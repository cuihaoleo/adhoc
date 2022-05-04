#!/usr/bin/env python3
"""
Copy directories while keeping reflinks.
"""

import argparse
import array
import fcntl
import logging
import os
import shutil
import struct
import subprocess

STRUCT_FIEMAP = struct.Struct("=QQLLLL")
STRUCT_FIEMAP_EXTENT = struct.Struct('=QQQQQLLLL')
FIEMAP_FLAG_SYNC = 0x00000001
FIEMAP_EXTENT_LAST = 0x00000001
FIEMAP_EXTENT_SHARED = 0x00002000
FS_IOC_FIEMAP = 0xC020660B


def get_fiemap_extents(path):
    with open(path) as fd:
        num_of_extents = 0

        # Two ioctl calls: first to get extent counts, second to get extent structs
        for _ in range(2):
            array_size = STRUCT_FIEMAP.size + num_of_extents * STRUCT_FIEMAP_EXTENT.size
            buffer = array.array('B', [0] * array_size)

            STRUCT_FIEMAP.pack_into(
                buffer, 0,
                0,                   # fm_start
                0xFFFFFFFFFFFFFFFF,  # fm_length
                FIEMAP_FLAG_SYNC,    # fm_flags
                0,                   # fm_mapped_extents (OUT)
                num_of_extents,      # fm_extent_count
                0                    # fm_reserved
            )

            if fcntl.ioctl(fd, FS_IOC_FIEMAP, buffer) < 0:
                raise IOError("ioctl failed")

            _, _, _, num_of_extents, _, _ = STRUCT_FIEMAP.unpack_from(buffer, 0)

            if num_of_extents == 0:
                # May happen if file is sparse
                return None

    offset = STRUCT_FIEMAP.size
    extents = []

    for _ in range(num_of_extents):
        fe_logical, fe_physical, fe_length, _, _, fe_flags, _, _, _ = \
            STRUCT_FIEMAP_EXTENT.unpack_from(buffer[offset:offset + STRUCT_FIEMAP_EXTENT.size])

        if not(fe_flags & FIEMAP_EXTENT_SHARED):
            # Ensure all extents are shared. May be too restrictive
            return None

        extents.append((fe_logical, fe_physical, fe_length))
        offset += STRUCT_FIEMAP_EXTENT.size

    if not(fe_flags & FIEMAP_EXTENT_LAST):
        # If not, likely the file changed between two ioctl calls?
        return None

    return tuple(extents)


def copy_file_attributes(src, dst):
    """Improved copystat to keep file owner as well"""
    shutil.copystat(src, dst)
    st = os.lstat(src)
    os.chown(dst, st.st_uid, st.st_gid, follow_symlinks=False)


class CopyHelper:
    def __init__(self):
        self.file_mapping = dict()

    def __copy_symlink(self, src, dst):
        if os.path.exists(dst):
            os.unlink(dst)

        linkto = os.readlink(src)
        logging.info("COPY LINK: %r (%r) -> %r", src, linkto, dst)

        os.symlink(linkto, dst)
        copy_file_attributes(src, dst)

    def __copy_regular_file(self, src, dst):
        extents = get_fiemap_extents(src)
        reflink_from = self.file_mapping.get(extents)

        if os.path.exists(dst):
            src_stat = os.lstat(src)
            dst_stat = os.lstat(dst)

            for attr in "st_mode", "st_uid", "st_gid", "st_size", "st_mtime":
                if getattr(src_stat, attr) != getattr(dst_stat, attr):
                    break
            else:
                logging.info("SKIP: %r", dst)
                return

        if reflink_from is None and extents is not None:
            self.file_mapping[extents] = dst

        logging.info("COPY: %r -> %r", src, dst)

        if reflink_from is None:
            shutil.copy(src, dst)
            copy_file_attributes(src, dst)
        else:
            logging.info("REFLINK: %r -> %r", reflink_from, dst)
            cmd = ["/bin/cp", "--reflink=always", reflink_from, dst]
            subprocess.check_call(cmd)
            copy_file_attributes(src, dst)

    def copy(self, src_dir, dst_dir):
        def do_copy(src, dst):
            if os.path.islink(src):
                self.__copy_symlink(src, dst)
            elif os.path.isfile(src):
                self.__copy_regular_file(src, dst)
            else:
                logging.warning("Unknown file type: %r", src)

        def copy_dir_metadata(src, dst):
            """Copy fs attributes of directories because copytree doesn't do this."""
            logging.info("COPY METADATA: %r -> %r", src, dst)
            copy_file_attributes(src, dst)

            for entry in os.scandir(src):
                if entry.is_dir():
                    next_src = os.path.join(src, entry.name)
                    next_dst = os.path.join(dst, entry.name)
                    copy_dir_metadata(next_src, next_dst)

        shutil.copytree(
            src_dir, dst_dir,
            copy_function=do_copy,
            dirs_exist_ok=True,
            symlinks=False  # handle symlinks ourselves
        )

        copy_dir_metadata(src_dir, dst_dir)


def main():
    logging.basicConfig(format='%(asctime)s [%(levelname)s] %(message)s', level=logging.INFO)

    parser = argparse.ArgumentParser(description="Reflink-aware directory copy script")
    parser.add_argument('source_dirs', metavar="SOURCE", nargs='+')
    parser.add_argument('dest_dir', metavar="DEST")
    args = parser.parse_args()

    helper = CopyHelper()

    if len(args.source_dirs) == 1:
        helper.copy(args.source_dirs[0], args.dest_dir)
    else:
        for d in args.source_dirs:
            name = os.path.basename(os.path.realpath(d))
            helper.copy(d, os.path.join(args.dest_dir, name))


if __name__ == "__main__":
    main()
