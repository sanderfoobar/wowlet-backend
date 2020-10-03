# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2020, The Monero Project.
# Copyright (c) 2020, dsc@xmr.pm

import re, os, sys, requests

current_height = 664767
f = open("heights.txt", "a")
for i in range(0, current_height, 1500):
    if i == 0:
        i = 1
    if i % (1500*8) == 0:
        print(f"[*] {current_height-i}")

    url = f"https://stagenet.xmrchain.net/block/{i}"
    resp = requests.get(url, headers={"User-Agent": "Feather"})
    resp.raise_for_status()
    content = resp.content.decode()
    timestamp = wow = re.findall(r"\((\d{10})\)", content)[0]
    f.write(f"{i}:{timestamp}\n")

f.close()
