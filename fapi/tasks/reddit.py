# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2020, The Monero Project.
# Copyright (c) 2020, dsc@xmr.pm

import settings
from fapi.utils import httpget
from fapi.tasks import FeatherTask


class RedditTask(FeatherTask):
    def __init__(self, interval: int = 900):
        from fapi.factory import app
        super(RedditTask, self).__init__(interval)

        self._cache_key = "reddit"
        self._cache_expiry = self.interval * 10

        self._websocket_cmd = "reddit"

        self._http_endpoints = {
            "xmr": "https://www.reddit.com/r/monero",
            "wow": "https://www.reddit.com/r/wownero",
            "aeon": "https://www.reddit.com/r/aeon",
            "trtl": "https://www.reddit.com/r/TRTL",
            "xhv": "https://www.reddit.com/r/havenprotocol",
            "loki": "https://www.reddit.com/r/LokiProject"
        }

        if settings.COIN_SYMBOL not in self._http_endpoints:
            app.logger.warning(f"Missing Reddit URL for {settings.COIN_SYMBOL.upper()}, ignoring update task")
            self._active = False

        self._http_endpoint = self._http_endpoints[settings.COIN_SYMBOL]
        if self._http_endpoint.endswith("/"):
            self._http_endpoint = self._http_endpoint[:-1]

    async def task(self):
        from fapi.factory import app

        url = f"{self._http_endpoint}/new.json?limit=15"
        try:
            blob = await httpget(url, json=True, raise_for_status=True)
        except Exception as ex:
            app.logger.error(f"failed fetching '{url}' {ex}")
            raise

        blob = [{
            'title': z['data']['title'],
            'author': z['data']['author'],
            'url': "https://old.reddit.com" + z['data']['permalink'],
            'comments': z['data']['num_comments']
        } for z in blob['data']['children']]
        if not blob:
            raise Exception("no content")

        return blob
