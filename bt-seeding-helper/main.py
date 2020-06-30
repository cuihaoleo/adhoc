#!/usr/bin/env python3

import os
import sys
import time
import base64
import bisect

from bitarray import bitarray
import transmissionrpc

from torrent_file import TorrentFile


def dir_traveller(*dir_list):
    dedup_list = set()
    for path in dir_list:
        for dirpath, dirnames, filenames in os.walk(path):
            for item in filenames:
                fullpath = os.path.realpath(os.path.join(dirpath, item))
                stat = os.stat(fullpath)
                dedup_info = (stat.st_dev, stat.st_ino)
                if dedup_info not in dedup_list:
                    dedup_list.add(dedup_info)
                    yield (fullpath, stat.st_size)


def main():
    torrent_path = sys.argv[1]
    target_dir = os.path.realpath(sys.argv[2])
    source_dirs = sys.argv[3:]

    if not os.path.isdir(target_dir):
        raise Exception("target_dir not found!")

    torrent = TorrentFile(torrent_path)
    with open(torrent_path, "rb") as fin:
        torrent_data = base64.b64encode(fin.read()).decode("utf8")

    transmission = transmissionrpc.Client('localhost', port=9091)
    for tor in transmission.get_torrents():
        info_hash = tor._fields["hashString"].value
        if info_hash == torrent.info_hash:
            print("Already in download queue!")
            sys.exit(0)

    pool = sorted((a, b) for b, a in dir_traveller(*source_dirs))
    candidates = []

    for bt_file, length in torrent.get_files():
        idx = bisect.bisect_right(pool, (length, ""))
        match_files = set()

        while idx < len(pool) and pool[idx][0] == length:
            match_files.add(pool[idx][1])
            idx += 1

        candidates.append(match_files)

    def dfs_verify(depth, mask):
        sys.stdout.write("\rDepth: %d/%d" % (depth, len(candidates)))
        if depth == len(candidates):
            return

        for item in candidates[depth]:
            order[depth] = item
            success, result = torrent.verify(order, mask, True)
            if success:
                dfs_verify(depth + 1, mask & ~result)
                break
        else:
            order[depth] = None
            #dfs_verify(depth + 1, mask)

    order = [None] * len(candidates)
    mask0 = bitarray(torrent.piece_num)
    mask0.setall(True)

    print("DFS verify is running...")
    sys.setrecursionlimit(max(sys.getrecursionlimit(), len(candidates) * 2))
    dfs_verify(0, mask0)

    print("\nResult:")
    unwanted = []
    wanted = []
    have_a_piece = False
    for idx, (_, length) in enumerate(torrent.get_files()):
        path = order[idx]
        if path is None:
            print(" FILE%d not found" % idx)
            unwanted.append(idx)
        else:
            print(" FILE%d: %s" % (idx, path))
            have_a_piece |= length > 2 * torrent.piece_length
            wanted.append(idx)

    if not have_a_piece or any(item is None for item in order):
        print("Nothing found!")
        sys.exit(-1)

    data_dir = os.path.join(target_dir, torrent.info_hash)
    for real_path, (target_path, _) in zip(order, torrent.get_files()):
        dest = os.path.join(data_dir, *target_path)
        os.makedirs(os.path.dirname(dest), exist_ok=True)

        if real_path is None:
            os.chmod(os.path.dirname(dest), 0o777)
            continue

        os.symlink(real_path, dest)
        print("Link {} to {}".format(real_path, dest))

    os.chmod(data_dir, 0o555)
    tor = transmission.add_torrent(torrent_data,
                                   download_dir=data_dir,
                                   files_wanted=wanted,
                                   files_unwanted=unwanted)
    tor_id = tor._fields['id'].value

    tor = transmission.get_torrent(tor_id)
    info_hash = tor._fields["hashString"].value
    if info_hash == torrent.info_hash:
        print("Torrent added to transmission queue!")
        print("Wait for checking...")

    while tor.status in ["checking", "check pending"]:
        tor = transmission.get_torrent(tor_id)
        time.sleep(1)

    if tor.status != "seeding":
        try:
            raise Exception("Not seeding (status=%s)." % tor.status)
        except Exception:
            tor.stop()
            raise
    else:
        print("Torrent is in seeding status. I've done everything.")


if __name__ == "__main__":
    main()
