# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2020, The Monero Project.
# Copyright (c) 2020, dsc@xmr.pm

from bs4 import BeautifulSoup
from typing import List
from dateutil.parser import parse

import settings
from wowlet_backend.utils import httpget
from wowlet_backend.tasks import WowletTask


class ForumThreadsTask(WowletTask):
    """Fetch recent forum threads."""
    def __init__(self, interval: int = 300):
        from wowlet_backend.factory import app
        super(ForumThreadsTask, self).__init__(interval)

        self._cache_key = "forum"
        self._cache_expiry = self.interval * 10

        # url
        self._http_endpoint = "https://forum.wownero.com/latest.json"

        self._websocket_cmd = "forum"

    async def task(self):
        from wowlet_backend.factory import app

        blob = await httpget(self._http_endpoint, json=True)

        users = {z['id']: z for z in blob["users"]}

        topics = []
        for topic in blob['topic_list']['topics']:
            if topic.get("pinned_globally", True):
                continue

            try:
                u = next(z for z in topic["posters"] if "original poster" in z['description'].lower())['user_id']
                href = f"https://forum.wownero.com/t/{topic['slug']}"
                topics.append({
                    "id": topic["id"],
                    "title": topic["title"],
                    "comments": topic["posts_count"] - 1,
                    "created_at": parse(topic["created_at"]).strftime("%Y-%m-%d %H:%M"),
                    "author": users[u]['username'],
                    "permalink": href
                })
            except Exception as ex:
                app.logger.error(f"skipping a forum topic; {ex}")

        return topics[:25]
