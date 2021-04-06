# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2020, The Monero Project.
# Copyright (c) 2020, dsc@xmr.pm

import random
import time
import json
from datetime import datetime, timedelta
from typing import Dict, Union, Optional
from copy import deepcopy
import asyncio
import re

from wowlet_backend.utils import RE_ADDRESS


PIN_SPACE_AMOUNT = list(range(1, 10000))
PIN_CODES = {str(k): None for k in PIN_SPACE_AMOUNT}


class WebsocketParse:
    @staticmethod
    async def parser(cmd: str, data=None):
        if cmd == "txFiatHistory":
            return await WebsocketParse.txFiatHistory(data)
        elif cmd == "requestPIN":
            return await WebsocketParse.requestPIN(data)
        elif cmd == "lookupPIN":
            return await WebsocketParse.lookupPIN(data)

    @staticmethod
    async def txFiatHistory(data=None):
        if not data or not isinstance(data, dict):
            return
        if "year" not in data or not isinstance(data['year'], int):
            return
        if "month" in data and not isinstance(data['month'], int):
            return

        year = data.get('year')
        month = data.get('month')

        from wowlet_backend.tasks.historical_prices import HistoricalPriceTask
        return await HistoricalPriceTask.get(year, month)

    @staticmethod
    async def requestPIN(data=None) -> str:
        from wowlet_backend.factory import cache
        if not data or not isinstance(data, dict):
            return ""
        if "address" not in data or not isinstance(data['address'], str):
            return ""
        if "signature" not in data or not isinstance(data['signature'], str):
            return ""
        signature = data.get('signature')
        address = data.get('address')
        if not re.match(RE_ADDRESS, address) or not signature.startswith("Sig"):
            return ""

        cache_key_address = f"pin_{address}"
        cache_key_lookups = "pin_space"
        ttl = 600

        lock = asyncio.Lock()
        async with lock:
            result = await cache.get(cache_key_address)
            if result:
                return result.decode().zfill(4)

            lookups = await cache.get(cache_key_lookups)
            if not lookups:
                await cache.set(cache_key_lookups, json.dumps(PIN_CODES).encode())
                lookups: Dict[str, Optional[dict]] = PIN_CODES
            else:
                lookups: Dict[str, Optional[dict]] = json.loads(lookups)

            space = deepcopy(PIN_SPACE_AMOUNT)
            random.shuffle(space)
            now = int(time.time())

            for number in space:
                _blob = lookups[str(number)]
                if _blob:
                    until = _blob.get('until')
                    if now > until:
                        _blob = None  # expired, mark as writeable

                if not _blob:
                    valid_until = int(time.time()) + ttl
                    lookups[str(number)] = {
                        "address": address,
                        "until": valid_until
                    }

                    await cache.setex(cache_key_address, ttl, number)
                    await cache.set(cache_key_lookups, json.dumps(lookups).encode())
                    return str(number).zfill(4)
            return ""

    @staticmethod
    async def lookupPIN(data=None) -> dict:
        from wowlet_backend.factory import cache
        if not data or not isinstance(data, dict):
            return {}
        if "PIN" not in data or not isinstance(data['PIN'], str) or not len(data['PIN']) == 4:
            return {}
        PIN = data['PIN']
        if not re.match("^\d{4}$", PIN):
            return {}

        cache_key_lookups = "pin_space"
        lookups = await cache.get(cache_key_lookups)
        if not lookups:
            await cache.set(cache_key_lookups, json.dumps(PIN_CODES).encode())
            lookups: Dict[str, Optional[dict]] = PIN_CODES
        else:
            lookups: Dict[str, Optional[dict]] = json.loads(lookups)

        blob = lookups.get(str(int(PIN)))
        if not blob:
            return {"address": "", "PIN": PIN}  # undefined behavior

        address = blob.get('address')
        until = blob.get('until')

        now = int(time.time())
        if now > until:
            return {"address": "", "PIN": PIN}  # entry expired

        return {
            "address": address,
            "PIN": PIN
        }
