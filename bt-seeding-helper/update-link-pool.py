#!/usr/bin/env python3

import sys
import os
import pathlib


def main():
    base_dir = pathlib.Path(sys.argv[1])
    pool_dir = base_dir.joinpath(".pool")
    pool_dir.mkdir(0o755, exist_ok=True)

    dedup_list = set()
    for f in pool_dir.iterdir():
        if not f.is_file() or f.is_symlink():
            continue

        stat = f.lstat()
        if stat.st_nlink <= 1:
            print("DEL:", f)
            f.unlink()
        else:
            dedup_list.add(stat.st_ino)

    for dirpath, dirnames, filenames in os.walk(base_dir):
        for item in filenames:
            path = os.path.join(dirpath, item)
            rel = os.path.relpath(path, start=base_dir)

            for c in rel.split(os.path.sep):
                if c.startswith("."):
                    print("EXCLUDE:", path)
                    break
            else:
                ino = os.stat(path).st_ino
                if ino in dedup_list:
                    print("SKIP:", path)
                    continue

                try:
                    os.link(path, pool_dir.joinpath("%x.ln" % ino))
                except PermissionError:
                    pass
                else:
                    dedup_list.add(ino)
                    print("ADD:", path)


if __name__ == "__main__":
    main()
