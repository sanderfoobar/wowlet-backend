# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2020, The Monero Project.
# Copyright (c) 2020, dsc@xmr.pm

import re
from typing import Union
from collections import Counter
from functools import partial

import settings
from wowlet_backend.utils import httpget, popularity_contest
from wowlet_backend.tasks import FeatherTask


class BlockheightTask(FeatherTask):
    """
    Fetch latest blockheight using webcrawling. We pick the most popular
    height from a list of websites. Arguably this approach has benefits
    over querying a (local) Monero RPC instance, as that requires
    maintenance, while this solution assumes that (at least) 2 websites
    reports the correct height.
    """
    def __init__(self, interval: int = 60):
        super(BlockheightTask, self).__init__(interval)

        self._cache_key = "blockheights"
        self._cache_expiry = 90

        self._websocket_cmd = "blockheights"

        self._fns = {
            "xmr": {
                "mainnet": [
                    self._blockchair,
                    partial(self._onion_explorer, url="https://xmrchain.net/"),
                    partial(self._onion_explorer, url="https://community.xmr.to/explorer/mainnet/"),
                    partial(self._onion_explorer, url="https://monero.exan.tech/")
                ],
                "stagenet": [
                    partial(self._onion_explorer, url="https://stagenet.xmrchain.net/"),
                    partial(self._onion_explorer, url="https://community.xmr.to/explorer/stagenet/"),
                    partial(self._onion_explorer, url="https://monero-stagenet.exan.tech/")
                ]
            },
            "wow": {
                "mainnet": [
                    partial(self._onion_explorer, url="https://explore.wownero.com/"),
                ]
            },
            "aeon": {
                "mainnet": [
                    partial(self._onion_explorer, url="https://aeonblockexplorer.com/"),
                ],
                "stagenet": [
                    partial(self._onion_explorer, url="http://162.210.173.151:8083/"),
                ]
            },
            "trtl": {
                "mainnet": [
                    self._turtlenode,
                    self._turtlenetwork,
                    self._l33d4n
                ]
            },
            "xhv": {
                "mainnet": [
                    partial(self._onion_explorer, url="https://explorer.havenprotocol.org/")
                ],
                "stagenet": [
                    partial(self._onion_explorer, url="https://explorer.stagenet.havenprotocol.org/page/1")
                ]
            },
            "loki": {
                "mainnet": [
                    partial(self._onion_explorer, url="https://lokiblocks.com/")
                ],
                "testnet": [
                    partial(self._onion_explorer, url="https://lokitestnet.com/")
                ]
            }
        }

    async def task(self) -> Union[dict, None]:
        from wowlet_backend.factory import app
        coin_network_types = ["mainnet", "stagenet", "testnet"]
        data = {t: 0 for t in coin_network_types}

        for coin_network_type in coin_network_types:
            if coin_network_type not in self._fns[settings.COIN_SYMBOL]:
                continue

            heights = []
            for fn in self._fns[settings.COIN_SYMBOL][coin_network_type]:
                fn_name = fn.func.__name__ if isinstance(fn, partial) else fn.__name__

                try:
                    result = await fn()
                    heights.append(result)
                except Exception as ex:
                    app.logger.error(f"blockheight fetch failed from {fn_name}(): {ex}")
                    continue

            if heights:
                data[coin_network_type] = popularity_contest(heights)

        if data["mainnet"] == 0:  # only care about mainnet
            app.logger.error(f"Failed to parse latest blockheight!")
            return

        return data

    async def _blockchair(self) -> int:
        re_blockheight = r"<a href=\".*\">(\d+)</a>"

        url = "https://blockchair.com/monero"
        content = await httpget(url, json=False, raise_for_status=True)

        height = re.findall(re_blockheight, content)
        height = max(map(int, height))
        return height

    async def _wownero(self) -> int:
        url = "https://explore.wownero.com/"
        return await BlockheightTask._onion_explorer(url)

    async def _turtlenode(self) -> int:
        url = "https://public.turtlenode.net/info"
        blob = await httpget(url, json=True, raise_for_status=True)
        height = int(blob.get("height", 0))
        if height <= 0:
            raise Exception("bad height")
        return height

    async def _turtlenetwork(self) -> int:
        url = "https://tnnode2.turtlenetwork.eu/blocks/height"
        blob = await httpget(url, json=True, raise_for_status=True)
        height = int(blob.get("height", 0))
        if height <= 0:
            raise Exception("bad height")
        return height

    async def _l33d4n(self):
        url = "https://blockapi.turtlepay.io/block/header/top"
        blob = await httpget(url, json=True, raise_for_status=True)
        height = int(blob.get("height", 0))
        if height <= 0:
            raise Exception("bad height")
        return height

    @staticmethod
    async def _onion_explorer(url):
        """
        Pages that are based on:
        https://github.com/moneroexamples/onion-monero-blockchain-explorer
        """
        re_blockheight = r"block\/(\d+)\"\>"
        content = await httpget(url, json=False)

        height = re.findall(re_blockheight, content)
        height = max(map(int, height))
        return height
