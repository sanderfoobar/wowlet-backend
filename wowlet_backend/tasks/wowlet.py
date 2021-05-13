# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2020, The Monero Project.
# Copyright (c) 2020, dsc@xmr.pm

from dateutil.parser import parse

import settings
from wowlet_backend.utils import httpget
from wowlet_backend.tasks import WowletTask


class WowletReleasesTask(WowletTask):
    """Fetches the latest Wowlet releases using gitea's API"""
    def __init__(self, interval: int = 3600):
        super(WowletReleasesTask, self).__init__(interval)

        self._cache_key = "wowlet_releases"
        self._cache_expiry = self.interval

        self._websocket_cmd = "wowlet_releases"

        self._http_endpoint = "https://git.wownero.com/api/v1/repos/wowlet/wowlet/releases?limit=1"

    async def task(self) -> dict:
        blob = await httpget(self._http_endpoint)
        if not isinstance(blob, list) or not blob:
            raise Exception(f"Invalid JSON response for {self._http_endpoint}")

        blob = blob[0]

        data = {}
        for asset in blob['assets']:
            operating_system = "linux"
            if "msvc" in asset['name'] or "win64" in asset['name'] or "windows" in asset['name']:
                operating_system = "windows"
            elif "macos" in asset["name"]:
                operating_system = "macos"

            data[operating_system] = {
                "name": asset["name"],
                "created_at": parse(asset["created_at"]).strftime("%Y-%m-%d"),
                "url": asset['browser_download_url'],
                "download_count": asset["download_count"],
                "size": asset['size']
            }

        tag = blob['tag_name']
        if tag.startswith("v"):
            tag = tag[1:]

        try:
            t = [int(z) for z in tag.split(".")]
            if len(t) != 3:
                raise Exception()
        except:
            raise Exception(f"invalid tag: {tag}")

        return {
            "assets": data,
            "body": blob['body'],
            "version": tag
        }
