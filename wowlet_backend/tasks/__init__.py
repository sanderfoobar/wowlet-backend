# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2020, The Monero Project.
# Copyright (c) 2020, dsc@xmr.pm

import json
import asyncio
import random
from typing import Union


class FeatherTask:
    """
    The base class of many recurring tasks for this
    project. This abstracts away some functionality:

    1. Tasks are automatically cached in Redis if the `_cache_key` is set.
    2. The task result is propagated to connected websocket clients if
       `_websocket_cmd` is set.
    3. Inheritors should implement the `task()` method.
    4. Inheritors can optionally implement the `done()` method.
    """
    def __init__(self, interval: int):
        """
        :param interval: secs
        """
        self.interval = interval

        # propogate to websocket clients?
        self._websocket_cmd: str = None

        # redis
        self._cache_key: str = None
        self._cache_expiry: int = None

        # logging
        self._qualname: str = f"{self.__class__.__module__}.{self.__class__.__name__}"

        self._active = True
        self._running = False

    async def start(self, *args, **kwargs):
        from wowlet_backend.factory import app, connected_websockets
        if not self._active:
            # invalid task
            return

        app.logger.info(f"Starting task {self._qualname}")
        sleep = lambda: asyncio.sleep(random.randrange(self.interval - 5,
                                                       self.interval + 5))
        while True:
            if not self._active:
                # invalid task
                return

            if self._running:
                # task already running, wait for completion
                await asyncio.sleep(5)
                continue

            try:
                self._running = True
                result: dict = await self.task(*args, **kwargs)
                if not result:
                    raise Exception("No result")
            except Exception as ex:
                app.logger.error(f"{self._qualname} - {ex}")

                # if the task failed we can attempt to use an old value from the cache.
                if not self._cache_key:
                    app.logger.warning(f"{self._qualname} - No cache key for task, skipping")
                    await sleep()
                    self._running = False
                    continue

                app.logger.info(f"{self._qualname} - trying cache")
                result = await self.cache_get(self._cache_key)
                if result:
                    app.logger.warning(f"serving cached result for {self._qualname}")
                else:
                    app.logger.error(f"{self._qualname} - cache lookup failed, fix me")
                    await sleep()
                    self._running = False
                    continue

            # optional: propogate result to websocket peers
            if self._websocket_cmd and result:
                # but only when there is a change
                normalize = lambda k: json.dumps(k, sort_keys=True, indent=4)
                propagate = True

                cached = await self.cache_get(self._cache_key)
                if cached:
                    if normalize(cached) == normalize(result):
                        propagate = False

                if propagate:
                    for queue in connected_websockets:
                        await queue.put({
                            "cmd": self._websocket_cmd,
                            "data": result
                        })

            # optional: cache the result
            if self._cache_key and result:
                await self.cache_set(self._cache_key, result, self._cache_expiry)

            # optional: call completion function
            if 'done' in self.__class__.__dict__:
                await self.done(result)

            await sleep()
            self._running = False

    async def task(self, *args, **kwargs):
        raise NotImplementedError()

    async def done(self, *args, **kwargs):
        """overload this method to execute this function after
        completion of `task`. Results from `task` are parameters
        for `done`."""
        raise NotImplementedError()

    async def end(self, result: dict):
        raise NotImplementedError()

    async def cache_json_get(self, key: str, path="."):
        from wowlet_backend.factory import app, cache

        try:
            data = await cache.execute('JSON.GET', key, path)
            if data:
                return json.loads(data)
        except Exception as ex:
            app.logger.error(f"Redis error: {ex}")

    async def cache_get(self, key: str) -> dict:
        from wowlet_backend.factory import app, cache

        try:
            data = await cache.get(key)
            if not data:
                return {}
            return json.loads(data)
        except Exception as ex:
            app.logger.error(f"Redis GET error with key '{key}': {ex}")

    async def cache_set(self, key, val: Union[dict, int], expiry: int = 0) -> bool:
        from wowlet_backend.factory import app, cache
        try:
            data = json.dumps(val)
            if isinstance(expiry, int) and expiry > 0:
                await cache.setex(key, expiry, data)
            else:
                await cache.set(key, data)
            return True
        except Exception as ex:
            app.logger.error(f"Redis SET error with key '{key}': {ex}")


from wowlet_backend.tasks.proposals import FundingProposalsTask
from wowlet_backend.tasks.historical_prices import HistoricalPriceTask
from wowlet_backend.tasks.blockheight import BlockheightTask
from wowlet_backend.tasks.rates_fiat import FiatRatesTask
from wowlet_backend.tasks.rates_crypto import CryptoRatesTask
from wowlet_backend.tasks.reddit import RedditTask
from wowlet_backend.tasks.rpc_nodes import RPCNodeCheckTask
from wowlet_backend.tasks.xmrig import XmrigTask
from wowlet_backend.tasks.xmrto import XmrToTask
