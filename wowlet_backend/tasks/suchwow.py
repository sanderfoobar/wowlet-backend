# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2020, The Monero Project.
# Copyright (c) 2020, dsc@xmr.pm

import json
import os
import re
import glob

import magic
import aiohttp
import aiofiles
from bs4 import BeautifulSoup

import settings
from wowlet_backend.utils import httpget, image_resize
from wowlet_backend.tasks import FeatherTask


class SuchWowTask(FeatherTask):
    def __init__(self, interval: int = 600):
        """
        This task is specifically for Wownero - fetching a listing
        of recent SuchWow submissions.
        """
        super(SuchWowTask, self).__init__(interval)

        self._cache_key = "suchwow"
        self._cache_expiry = self.interval * 10

        self._http_endpoint = "https://suchwow.xyz/"
        self._tmp_dir = os.path.join(settings.cwd, "data", "suchwow")

        if not os.path.exists(self._tmp_dir):
            os.mkdir(self._tmp_dir)

    async def task(self):
        from wowlet_backend.factory import app
        result = await httpget(f"{self._http_endpoint}api/list", json=True)

        result = list(sorted(result, key=lambda k: k['id'], reverse=True))
        result = result[:15]

        for post in result:
            post_id = int(post['id'])
            path_img = os.path.join(self._tmp_dir, f"{post_id}.jpg")
            path_img_thumb = os.path.join(self._tmp_dir, f"{post_id}.thumb.jpg")
            path_img_tmp = os.path.join(self._tmp_dir, f"{post_id}.tmp.jpg")
            path_metadata = os.path.join(self._tmp_dir, f"{post_id}.json")
            if os.path.exists(path_metadata):
                continue

            try:
                url = post['image']
                await self.download_and_write(url, path_img_tmp)

                async with aiofiles.open(path_img_tmp, mode="rb") as f:
                    image = await f.read()

                # security: only images
                if not await self.is_image(image):
                    app.logger.error(f"skipping {post_id} because of invalid mimetype")

                resized = await image_resize(image, max_bounding_box=800, quality=80)
                thumbnail = await image_resize(image, max_bounding_box=400, quality=80)

                async with aiofiles.open(path_img, mode="wb") as f:
                    await f.write(resized)

                async with aiofiles.open(path_img_thumb, mode="wb") as f:
                    await f.write(thumbnail)

            except Exception as ex:
                app.logger.error(f"Failed to download or resize {post_id}, cleaning up leftover files. {ex}")
                for path in [path_img, path_img_tmp, path_img_thumb]:
                    if os.path.exists(path):
                        os.unlink(path)
                continue

            f = open(path_metadata, "w")
            f.write(json.dumps({
                "img": os.path.basename(path_img),
                "thumb": os.path.basename(path_img_thumb),
                "added_by": post['submitter'].replace("<", ""),
                "addy": post['address'],
                "title": post['title'].replace("<", ""),
                "href": post['href'],
                "id": post['id']
            }))
            f.close()

        images = []
        try:
            for fn in glob.glob(f"{self._tmp_dir}/*.json", recursive=False):
                async with aiofiles.open(fn, mode="rb") as f:
                    blob = json.loads(await f.read())
                    images.append(blob)
        except Exception as ex:
            pass

        # sort on id, limit
        images = list(sorted(images, key=lambda k: k['id'], reverse=True))
        images = images[:15]

        return images

    async def download_and_write(self, url: str, destination: str):
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    raise Exception(f"Failed to download image from {url}; status non 200")
                f = await aiofiles.open(destination, mode='wb')
                await f.write(await resp.read())
                await f.close()

    async def is_image(self, buffer: bytes):
        mime = magic.from_buffer(buffer, mime=True)
        if mime in ["image/jpeg", "image/jpg", "image/png"]:
            return True
