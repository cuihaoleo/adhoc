import os
import hashlib
import datetime as dt

import bencoder
from bitarray import bitarray

from io_helper import ReadHelper, DummyReader


def _decode_dict_keys(d, encoding="utf8"):
    if isinstance(d, dict):
        new_dict = dict()
        for k in d.keys():
            if isinstance(k, bytes):
                newk = k.decode(encoding)
            new_dict[newk] = _decode_dict_keys(d[k], encoding)
        return new_dict
    elif isinstance(d, list):
        return [_decode_dict_keys(item, encoding) for item in d]
    else:
        return d


def _bytes_helper(dict_, key, encoding="utf8"):
    try:
        raw = dict_[key]
    except KeyError:
        return None
    else:
        return raw.decode(encoding)


class TorrentFile:
    def __init__(self, path):
        with open(path, "rb") as fin:
            raw_dict = bencoder.decode(fin.read())

        info_raw = bencoder.encode(raw_dict[b"info"])
        self._encoding = raw_dict.get(b"encoding", b"utf8").decode()
        self._encoding = self._encoding or "utf8"
        self._info_hash = hashlib.sha1(info_raw).hexdigest()

        self._dict = _decode_dict_keys(raw_dict, self._encoding)

        self._files = []
        if "files" in self._dict["info"]:
            self._total_length = 0
            for item in self._dict["info"]["files"]:
                path = [self.name]
                path.extend(i.decode(self._encoding) for i in item["path"])
                self._files.append((tuple(path), item["length"]))
                self._total_length += item["length"]
        else:
            self._total_length = self._dict["info"]["length"]
            self._files.append(((self.name,), self._total_length))

    @property
    def info_hash(self):
        return self._info_hash

    @property
    def comment(self):
        return _bytes_helper(self._dict, "comment", self._encoding)

    @property
    def created_by(self):
        return _bytes_helper(self._dict, "created by", self._encoding)

    @property
    def name(self):
        return _bytes_helper(self._dict["info"], "name", self._encoding)

    @property
    def source(self):
        return _bytes_helper(self._dict["info"], "source", self._encoding)

    @property
    def creation_date(self):
        try:
            epoch = self._dict["creation date"]
        except KeyError:
            return None
        else:
            obj = dt.datetime.fromtimestamp(epoch)
            return obj

    @property
    def announce(self):
        if "announce-list" in self._dict:
            result = []
            for tier in self._dict["announce-list"]:
                row = [r.decode(self._encoding) for r in tier]
                result.append(row)
            return result
        elif "announce" in self._dict:
            url = self._dict["announce"].decode(self._encoding)
            return [[url]]
        else:
            return None

    @property
    def piece_length(self):
        return self._dict["info"]["piece length"]

    @property
    def piece_num(self):
        up = self._total_length
        down = self.piece_length
        return (up + down - 1) // down

    @property
    def is_private(self):
        return self._dict["info"]["private"] != 0

    def get_piece_hash(self, n_piece):
        left = n_piece * 20
        right = left + 20
        sha1 = self._dict["info"]["pieces"][left:right]
        return sha1

    def get_files(self):
        yield from iter(self._files)

    def verify(self, files, mask=None, exit_on_fail=False):
        if mask is None:
            mask = bitarray(self.piece_num)
            mask.setall(True)
        else:
            mask = bitarray(mask)

        result = bitarray(self.piece_num)
        result.setall(False)

        if len(mask) != self.piece_num:
            raise ValueError("len(mask) != piece_num")

        if len(files) != len(self._files):
            raise ValueError("len(files) not match")

        fd_list = []
        acc_length = 0
        piece_length = self.piece_length
        for path, (_, length) in zip(files, self._files):
            if path is None or os.path.getsize(path) != length:
                first_piece = acc_length // piece_length
                acc_length += length
                last_piece = (acc_length - 1) // piece_length
                mask[first_piece:last_piece+1] = False
                fd_list.append(DummyReader(length))
            else:
                fd_list.append(open(path, "rb"))
                acc_length += length

        reader = ReadHelper(fd_list)
        gather_result = True
        idx = 0
        while idx < self.piece_num:
            if not mask[idx]:
                try:
                    idx += mask[idx:].index(1)
                except ValueError:
                    break
                else:
                    reader.seek(idx * piece_length)

            data = reader.read(piece_length)
            sha1 = hashlib.sha1(data).digest()

            match = (sha1 == self.get_piece_hash(idx))
            gather_result &= match
            result[idx] = match

            if exit_on_fail and not gather_result:
                break
            else:
                idx += 1

        reader.close()
        return gather_result, result
