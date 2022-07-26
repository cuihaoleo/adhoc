#!/usr/bin/env python3

import json
import subprocess
import tempfile
import argparse

parser = argparse.ArgumentParser(description="Simulate CrystalDiskMark using fio")
parser.add_argument("-n", "--loops", type=int, default=5,
                    help="Number of runs for each test.")
parser.add_argument("-s", "--size", type=int, default=1024,
                    help="IO size (in MiB) for each test.")
parser.add_argument("target", help="Test directory.")
args = parser.parse_args()

cmd = ["fio",
       "--loops=%d" % args.loops,
       "--direct=1",
       "--group_reporting",
       "--output-format=json",
       "--ioengine=libaio"]

all_tests = (("SEQ", 8, 1), ("SEQ", 1, 1), ("RND", 32, 16), ("RND", 1, 1))

for test_type, iodepth, numjobs in all_tests:
    name = "Q%dT%d" % (iodepth, numjobs)

    if test_type == "SEQ":
        name = "SEQ1M " + name
        prefix = ""
        bs = 1024
    else:
        name = "RND4K " + name
        prefix = "rand"
        bs = 4

    for rw in "read", "write":
        with tempfile.NamedTemporaryFile(dir=args.target) as fp:
            newcmd = cmd + [
                "--filename=" + fp.name,
                "--size=%d" % ((args.size << 20) // numjobs),
                "--name=" + name,
                "--bs=%dk" % bs,
                "--iodepth=%d" % iodepth,
                "--numjobs=%d" % numjobs,
                "--rw=%s" % (prefix + rw)]
            output = subprocess.check_output(newcmd)
        result = json.loads(output.decode())
        perf = result["jobs"][0][rw]

        try:
            bw_bytes = perf["bw_bytes"]
        except KeyError:
            bw_bytes = perf["bw"] * 1024

        bw_mib = bw_bytes / (1 << 20)
        iops = perf["iops"]

        print("%-12s %-5s : %10.2f MB/s" % (name, rw, bw_mib), end="")
        print("    [ %10.2f IOPS ]" % iops if prefix else "")
