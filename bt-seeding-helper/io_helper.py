import os
import io


class DummyReader:
    def __init__(self, length):
        self.length = length
        self.pos = 0

    def seek(self, pos, whence=0):
        if whence == os.SEEK_SET:
            self.pos = pos
        elif whence == os.SEEK_CUR:
            self.pos += pos
        elif whence == os.SEEK_END:
            self.pos = self.length + pos
        else:
            raise NotImplementedError
        return self.pos

    def read(self, size):
        raise NotImplementedError

    def close(self):
        pass


class ReadHelper:
    def __init__(self, fd_list):
        self.fd_list = list(fd_list)
        self.fd_len = []
        self.cur_fd = 0
        for fd in self.fd_list:
            length = fd.seek(0, os.SEEK_END)
            self.fd_len.append(length)
            fd.seek(0)

    def seek(self, pos, whence=0):
        if whence != os.SEEK_SET:
            raise NotImplementedError

        for idx, (fd, length) in enumerate(zip(self.fd_list, self.fd_len)):
            if pos < length:
                self.cur_fd = idx
                break
            else:
                pos -= length
        else:
            raise ValueError("Beyond EOF!")

        self.fd_list[self.cur_fd].seek(pos)

    def read(self, size):
        buf = io.BytesIO()
        while self.cur_fd < len(self.fd_list):
            data = self.fd_list[self.cur_fd].read(size - buf.tell())
            buf.write(data)
            if buf.tell() < size:
                self.cur_fd += 1
                try:
                    self.fd_list[self.cur_fd].seek(0)
                except IndexError:
                    break
            else:
                break
        return buf.getvalue()

    def close(self):
        for fd in self.fd_list:
            fd.close()
