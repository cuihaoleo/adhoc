#!/usr/bin/env python3
'''
Archive png files in compressed tar, avoiding double compression.

  $ find . -type f -name '*.png' > ../flist
  $ ./archive-png.py ../flist | zstd -T0 --ultra -22 --long -fo ../png.tar.zst
'''

import io
import os
import sys
import tarfile

from PIL import Image


def tar_filter(tarinfo):
    # For privacy...
    tarinfo.uid = tarinfo.gid = 0
    tarinfo.uname = tarinfo.gname = ''
    return tarinfo


def main():
    target_list_file = sys.argv[1]

    # Files to archive in the tarfile, one per line
    with open(target_list_file, 'rb') as fin:
        target_list = fin.read().splitlines()

    buf = io.BytesIO()
    Image.MAX_IMAGE_PIXELS = None  # Suppress warnings about big images

    with tarfile.open(
        fileobj=sys.stdout.buffer,
        mode='w|',
        format=tarfile.PAX_FORMAT,  # tar --posix
    ) as tar:
        for target in target_list:
            target = os.fsdecode(target)
            _, ext = os.path.splitext(target)

            if ext == '.png':
                tarinfo = tar.gettarinfo(target)

                if tarinfo.type == tarfile.REGTYPE:
                    im = Image.open(target)
                    buf.seek(0)
                    # Will Image.save preserve metadata?
                    im.save(buf, 'png', compress_level=0)
                    tarinfo.size = buf.tell()
                    buf.seek(0)

                    tar.addfile(tar_filter(tarinfo), fileobj=buf)
                else:
                    # Directory, symlink, hardlink...
                    tar.addfile(tar_filter(tarinfo))
            else:
                tar.add(target, filter=tar_filter)


if __name__ == '__main__':
    main()
