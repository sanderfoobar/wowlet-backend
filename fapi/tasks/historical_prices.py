# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2020, The Monero Project.
# Copyright (c) 2020, dsc@xmr.pm

import os
import json
from typing import List, Union
from datetime import datetime

import aiofiles

import settings
from fapi.utils import httpget
from fapi.tasks import FeatherTask


class HistoricalPriceTask(FeatherTask):
    """
    This class manages a historical price (USD) database, saved in a
    textfile at `self._path`. A Feather wallet instance will ask
    for the historical fiat price database on startup (but only
    in chunks of a month for anti-fingerprinting reasons).

    The task in this class simply keeps the fiat database
    up-to-date locally.
    """
    def __init__(self, interval: int = 43200):
        super(HistoricalPriceTask, self).__init__(interval)

        self._cache_key = f"historical_fiat"
        self._path = f"data/historical_prices_{settings.COIN_SYMBOL}.json"
        self._http_endpoint = f"https://www.coingecko.com/price_charts/{settings.COIN_NAME}/usd/max.json"

        self._year_genesis = int(settings.COIN_GENESIS_DATE[:4])

        self._load()

    async def task(self) -> Union[dict, None]:
        content = await httpget(self._http_endpoint, json=True, raise_for_status=False)
        if "stats" not in content:
            raise Exception()

        stats: List[List] = content.get('stats', [])  # [[timestamp,USD],]
        if not stats:
            return

        data = {
            year: {
                month: {} for month in range(1, 13)
            } for year in range(self._year_genesis, datetime.now().year + 1)
        }

        # timestamp:USD
        daily_price_blob = {day[0]: day[1] for day in stats}

        # normalize
        for timestamp, usd in daily_price_blob.items():
            _date = datetime.fromtimestamp(timestamp / 1000)
            data[_date.year].setdefault(_date.month, {})
            data[_date.year][_date.month][_date.day] = usd

        # update local database
        await self._write(data)
        return data

    async def _load(self) -> None:
        if not os.path.exists(self._path):
            return

        async with aiofiles.open(self._path, mode="r") as f:
            content = await f.read()
            blob = json.loads(content)

            # ¯\_(ツ)_/¯
            blob = {int(k): {
                int(_k): {
                    int(__k): __v for __k, __v in _v.items()
                } for _k, _v in v.items()
            } for k, v in blob.items()}

            await self.cache_set(self._cache_key, blob)

    async def _write(self, blob: dict) -> None:
        data = json.dumps(blob, sort_keys=True, indent=4)
        async with aiofiles.open(self._path, mode="w") as f:
            await f.write(data)

    @staticmethod
    async def get(year: int, month: int = None) -> Union[dict, None]:
        """This function is called when a Feather wallet client asks
        for (a range of) historical fiat information. It returns the
        data filtered by the parameters."""
        from fapi.factory import cache

        blob = await cache.get("historical_fiat")
        blob = json.loads(blob)
        if year not in blob:
            return

        rtn = {}
        if not month:
            for _m, days in blob[year].items():
                for day, price in days.items():
                    rtn[datetime(year, _m, day).strftime('%Y%m%d')] = price
            return rtn

        if month not in blob[year]:
            return

        for day, price in blob[year][month].items():
            rtn[datetime(year, month, day).strftime('%Y%m%d')] = price

        return rtn
