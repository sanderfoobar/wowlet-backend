# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2020, The Monero Project.
# Copyright (c) 2020, dsc@xmr.pm

import re
import json
import asyncio
import os
import random
from datetime import datetime
from collections import Counter
from functools import wraps
from typing import List, Union
from io import BytesIO

import psutil
import aiohttp
from aiohttp_socks import ProxyConnector
from PIL import Image

import settings


RE_ADDRESS = r"^[a-zA-Z0-9]{97}$"


def print_banner():
    print(f"""\033[91m
   _______________                        |*\_/*|________
  |  ___________  |     .-.     .-.      ||_/-\_|______  |
  | |           | |    .****. .****.     | |           | |
  | |   0   0   | |    .*****.*****.     | |   0   0   | |
  | |     -     | |     .*********.      | |     -     | |
  | |   \___/   | |      .*******.       | |   \___/   | |
  | |___     ___| |       .*****.        | |___________| |
  |_____|\_/|_____|        .***.         |_______________|
    _|__|/ \|_|_.............*.............._|________|_
   / ********** \                          / ********** \\
 /  ************  \                      /  ************  \\
--------------------       {settings.COIN_SYMBOL}          --------------------\033[0m
    """.strip())


def collect_websocket(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        from wowlet_backend.factory import connected_websockets
        queue = asyncio.Queue()
        connected_websockets.add(queue)
        try:
            return await func(queue, *args, **kwargs)
        finally:
            connected_websockets.remove(queue)
    return wrapper


async def httpget(url: str, json=True, timeout: int = 5, socks5: str = None, raise_for_status=True, verify_tls=True):
    headers = {"User-Agent": random_agent()}
    opts = {"timeout": aiohttp.ClientTimeout(total=timeout)}
    if socks5:
        opts['connector'] = ProxyConnector.from_url(socks5)

    async with aiohttp.ClientSession(**opts) as session:
        async with session.get(url, headers=headers, ssl=verify_tls) as response:
            if raise_for_status:
                response.raise_for_status()

            result = await response.json() if json else await response.text()
            if result is None or (isinstance(result, str) and result == ''):
                raise Exception("empty response from request")
            return result


def random_agent():
    from wowlet_backend.factory import user_agents
    return random.choice(user_agents)


async def feather_data():
    """A collection of data collected by
    `FeatherTask`, for Feather wallet clients."""
    from wowlet_backend.factory import cache, now
    data = await cache.get("data")
    if data:
        data = json.loads(data)
        return data

    keys = ["blockheights", "funding_proposals", "crypto_rates", "fiat_rates", "reddit", "rpc_nodes", "xmrig", "xmrto_rates", "suchwow", "forum"]
    data = {keys[i]: json.loads(val) if val else None for i, val in enumerate(await cache.mget(*keys))}

    # @TODO: for backward-compat reasons we're including some legacy keys which can be removed after 1.0 release
    data['nodes'] = data['rpc_nodes']
    data['ccs'] = data['funding_proposals']
    data['wfs'] = data['funding_proposals']

    # start caching when application lifetime is more than 20 seconds
    if (datetime.now() - now).total_seconds() > 20:
        await cache.setex("data", 30, json.dumps(data))
    return data


def popularity_contest(lst: List[int]) -> Union[int, None]:
    """Return most common occurrences of List[int]. If
    there are no duplicates, return max() instead.
    """
    if not lst:
        return
    if len(set(lst)) == len(lst):
        return max(lst)
    return Counter(lst).most_common(1)[0][0]


def current_worker_thread_is_primary() -> bool:
    """
    ASGI server (Hypercorn) may start multiple
    worker threads, but we only want one feather-ws
    instance to schedule `FeatherTask` tasks at an
    interval. Therefor this function determines if the
    current instance is responsible for the
    recurring Feather tasks.
    """
    from wowlet_backend.factory import app

    current_pid = os.getpid()
    parent_pid = os.getppid()
    app.logger.debug(f"current_pid: {current_pid}, "
                     f"parent_pid: {parent_pid}")

    if parent_pid == 0:
        return True

    parent = psutil.Process(parent_pid)
    if parent.name() != "hypercorn":
        return True

    lowest_pid = min(c.pid for c in parent.children(recursive=True) if c.name() == "hypercorn")
    if current_pid == lowest_pid:
        return True


async def image_resize(buffer: bytes, max_bounding_box: int = 512, quality: int = 70) -> bytes:
    """
    - Resize if the image is too large
    - PNG -> JPEG
    - Removes EXIF
    """
    buffer = BytesIO(buffer)
    buffer.seek(0)
    image = Image.open(buffer)
    image = image.convert('RGB')

    if max([image.height, image.width]) > max_bounding_box:
        image.thumbnail((max_bounding_box, max_bounding_box), Image.BICUBIC)

    data = list(image.getdata())
    image_without_exif = Image.new(image.mode, image.size)
    image_without_exif.putdata(data)

    buffer = BytesIO()
    image_without_exif.save(buffer, "JPEG", quality=quality)
    buffer.seek(0)

    return buffer.read()
