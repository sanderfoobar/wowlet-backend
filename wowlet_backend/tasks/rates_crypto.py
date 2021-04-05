# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2020, The Monero Project.
# Copyright (c) 2020, dsc@xmr.pm

from typing import List, Union

import settings
from wowlet_backend.utils import httpget
from wowlet_backend.tasks import FeatherTask


class CryptoRatesTask(FeatherTask):
    def __init__(self, interval: int = 180):
        super(CryptoRatesTask, self).__init__(interval)

        self._cache_key = "crypto_rates"
        self._cache_expiry = self.interval * 10

        self._websocket_cmd = "crypto_rates"

        self._http_api_gecko = "https://api.coingecko.com/api/v3"

    async def task(self) -> Union[List[dict], None]:
        """Fetch USD prices for various coins"""
        from wowlet_backend.factory import app

        url = f"{self._http_api_gecko}/coins/markets?vs_currency=usd"
        rates = await httpget(url, json=True)

        # normalize object, too many useless keys
        rates = [{
            "id": r["id"],
            "symbol": r["symbol"],
            "image": r["image"],
            "name": r["name"],
            "current_price": r["current_price"],
            "price_change_percentage_24h": r["price_change_percentage_24h"]
        } for r in rates]

        # additional coins as defined by `settings.CRYPTO_RATES_COINS_EXTRA`
        for coin, symbol in settings.CRYPTO_RATES_COINS_EXTRA.items():
            url = f"{self._http_api_gecko}/simple/price?ids={coin}&vs_currencies=usd"
            try:
                data = await httpget(url, json=True)
                if coin not in data or "usd" not in data[coin]:
                    continue

                rates.append({
                    "id": coin,
                    "symbol": symbol,
                    "image": "",
                    "name": coin.capitalize(),
                    "current_price": data[coin]["usd"],
                    "price_change_percentage_24h": 0.0
                })
            except Exception as ex:
                app.logger.error(f"extra coin: {coin}; {ex}")

        return rates
