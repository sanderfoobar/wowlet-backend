# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2020, The Monero Project.
# Copyright (c) 2020, dsc@xmr.pm

from dateutil.parser import parse

import settings
from wowlet_backend.utils import httpget
from wowlet_backend.tasks import FeatherTask


class XmrigTask(FeatherTask):
    """Fetches the latest XMRig releases using Github's API"""
    def __init__(self, interval: int = 43200):
        super(XmrigTask, self).__init__(interval)

        self._cache_key = "xmrig"
        self._cache_expiry = self.interval * 10

        self._websocket_cmd = "xmrig"

        self._http_endpoint = "https://api.github.com/repos/xmrig/xmrig/releases"

    async def task(self) -> dict:
        blob = await httpget(self._http_endpoint)
        if not isinstance(blob, list) or not blob:
            raise Exception(f"Invalid JSON response for {self._http_endpoint}")
        blob = blob[0]

        # only uploaded assets
        assets = list(filter(lambda k: k['state'] == 'uploaded', blob['assets']))

        # only archives
        assets = list(filter(lambda k: k['name'].endswith(('.tar.gz', '.zip')), assets))

        version = blob['tag_name']
        data = {}

        # sort by OS
        for asset in assets:
            operating_system = "linux"
            if "msvc" in asset['name'] or "win64" in asset['name']:
                operating_system = "windows"
            elif "macos" in asset["name"]:
                operating_system = "macos"

            data.setdefault(operating_system, [])
            data[operating_system].append({
                "name": asset["name"],
                "created_at": parse(asset["created_at"]).strftime("%Y-%m-%d"),
                "url": f"https://github.com/xmrig/xmrig/releases/download/{version}/{asset['name']}",
                "download_count": int(asset["download_count"])
            })

        return {
            "version": version,
            "assets": data
        }
