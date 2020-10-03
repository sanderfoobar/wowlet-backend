# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2020, The Monero Project.
# Copyright (c) 2020, dsc@xmr.pm

import asyncio
import json
import os
import re
import random
from functools import wraps
from datetime import datetime

import aiohttp


class BlockHeight:
    @staticmethod
    async def xmrchain(stagenet: bool = False):
        re_blockheight = r"block\/(\d+)\"\>"
        url = "https://stagenet.xmrchain.net/" if stagenet else "https://xmrchain.net/"
        content = await httpget(url, json=False)
        xmrchain = re.findall(re_blockheight, content)
        current = max(map(int, xmrchain))
        return current

    @staticmethod
    async def xmrto(stagenet: bool = False):
        re_blockheight = r"block\/(\d+)\"\>"
        url = "https://community.xmr.to/explorer/stagenet/" if stagenet else "https://community.xmr.to/explorer/mainnet/"
        content = await httpget(url, json=False)
        xmrchain = re.findall(re_blockheight, content)
        current = max(map(int, xmrchain))
        return current


async def loopyloop(secs: int, func, after_func=None):
    """
    asyncio loop
    :param secs: interval
    :param func: function to execute
    :param after_func: function to execute after completion
    :return:
    """
    while True:
        result = await func()
        if after_func:
            await after_func(result)

        # randomize a bit for Tor anti fingerprint reasons
        _secs = random.randrange(secs - 5, secs +5)
        await asyncio.sleep(_secs)


def collect_websocket(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        from fapi.factory import connected_websockets
        queue = asyncio.Queue()
        connected_websockets.add(queue)
        try:
            return await func(queue, *args, **kwargs)
        finally:
            connected_websockets.remove(queue)
    return wrapper


async def broadcast_blockheight():
    from fapi.factory import connected_websockets, api_data
    for queue in connected_websockets:
        await queue.put({
            "cmd": "blockheights",
            "data": {
                "height": api_data.get("blockheights", {})
            }
        })


async def broadcast_nodes():
    from fapi.factory import connected_websockets, api_data
    for queue in connected_websockets:
        await queue.put({
            "cmd": "nodes",
            "data": api_data['nodes']
        })


async def httpget(url: str, json=True):
    timeout = aiohttp.ClientTimeout(total=4)
    headers = {"User-Agent": random_agent()}
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url, headers=headers) as response:
            return await response.json() if json else await response.text()


def random_agent():
    from fapi.factory import user_agents
    return random.choice(user_agents)


class TxFiatDb:
    # historical fiat price db for given symbol
    def __init__(self, symbol, block_date_start):
        self.fn = "data/fiatdb"
        self.symbol = symbol
        self.block_start = block_date_start
        self._url = "https://www.coingecko.com/price_charts/69/usd/max.json"
        self.data = {}
        self.load()

    def get(self, year: int, month: int = None):
        rtn = {}
        if year not in self.data:
            return
        if not month:
            for _m, days in self.data[year].items():
                for day, price in days.items():
                    rtn[datetime(year, _m, day).strftime('%Y%m%d')] = price
            return rtn
        if month not in self.data[year]:
            return
        for day, price in self.data[year][month].items():
            rtn[datetime(year, month, day).strftime('%Y%m%d')] = price
        return rtn

    def load(self):
        if not os.path.exists("fiatdb"):
            return {}
        f = open("fiatdb", "r")
        data = f.read()
        f.close()
        data = json.loads(data)

        # whatever
        self.data = {int(k): {int(_k): {int(__k): __v for __k, __v in _v.items()} for _k, _v in v.items()} for k, v in data.items()}

    def write(self):
        f = open("fiatdb", "w")
        f.write(json.dumps(self.data))
        f.close()

    async def update(self):
        try:
            content = await httpget(self._url, json=True)
            if not "stats" in content:
                raise Exception()
        except Exception as ex:
            return

        stats = content.get('stats')
        if not stats:
            return

        year_start = int(self.block_start[:4])
        self.data = {z: {k: {} for k in range(1, 13)}
                     for z in range(year_start, datetime.now().year + 1)}
        content = {z[0]: z[1] for z in stats}

        for k, v in content.items():
            _date = datetime.fromtimestamp(k / 1000)
            self.data[_date.year].setdefault(_date.month, {})
            self.data[_date.year][_date.month][_date.day] = v

        self.write()
