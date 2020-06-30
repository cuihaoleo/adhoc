#!/usr/bin/env python3

import os
import re
import sys
import glob
import time
from urllib.parse import unquote

import requests
from bs4 import BeautifulSoup

target_dir = sys.argv[1]
if not os.path.isdir(target_dir):
    os.mkdir(target_dir)
os.chdir(target_dir)

s = requests.Session()

curl_str = input("Curl command: ")
cookie_key = "c_secure_uid", "c_secure_pass", "c_secure_ssl", "c_secure_login"
for key in cookie_key:
    m = re.search(r"%s=([^;']+)" % key, curl_str)
    val = m.group(1)
    s.cookies.set(name=key, value=val)

req = s.get("https://pt.sjtu.edu.cn/")
m = re.search(r"userdetails\.php\?id=([0-9]+)", req.text)
myid = m.group(1)

for status in ("seeding", "completed", "incomplete"):
    req = s.get("https://pt.sjtu.edu.cn/viewusertorrents.php",
                params={"id": myid, "show": status})
    print(status)
    soup = BeautifulSoup(req.text, "html.parser")
    for td in soup.find_all("td", class_="rowfollow"):
        a_elem = td.find("a")
        if a_elem is not None:
            m = re.search(r"id=([0-9]+)", a_elem["href"])
            tor_id = m.group(1)

            if glob.glob(tor_id + " - *.torrent"):
                continue

            print("  " + tor_id)
            req = s.get("https://pt.sjtu.edu.cn/download.php",
                        params={ "id": tor_id })
            cd = req.headers["content-disposition"]
            m = re.search("filename=(.+)", cd)
            fname = tor_id + " - " + unquote(m.group(1))
            with open(fname, "wb") as f:
                f.write(req.content)
            time.sleep(1)
