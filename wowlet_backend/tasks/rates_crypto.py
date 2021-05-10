# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2020, The Monero Project.
# Copyright (c) 2020, dsc@xmr.pm

from typing import List, Union

import settings
from wowlet_backend.utils import httpget
from wowlet_backend.tasks import WowletTask


class CryptoRatesTask(WowletTask):
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

        # limit the list, only include specific coins. see wowlet:src/utils/prices.cpp
        whitelist = ["XMR", "ZEC", "BTC", "ETH", "BCH", "LTC", "EOS", "ADA", "XLM", "TRX", "DASH", "DCR", "VET", "DOGE", "XRP", "WOW"]
        rates = [r for r in rates if r["symbol"].upper() in whitelist]

        # additional coins as defined by `settings.CRYPTO_RATES_COINS_EXTRA`
        for coin, symbol in settings.CRYPTO_RATES_COINS_EXTRA.items():
            obj = {}

            try:
                results = {}
                for vs_currency in ["usd", "btc"]:
                    url = f"{self._http_api_gecko}/simple/price?ids={coin}&vs_currencies={vs_currency}"
                    data = await httpget(url, json=True, timeout=15)
                    results[vs_currency] = data[coin][vs_currency]

                price_btc = "{:.8f}".format(results["btc"])
                price_sat = int(price_btc.replace(".", "").lstrip("0"))  # yolo

                obj = {
                    "id": coin,
                    "symbol": symbol,
                    "image": "",
                    "name": coin.capitalize(),
                    "current_price": results["usd"],
                    "current_price_btc": price_btc,
                    "current_price_satoshi": price_sat,
                    "price_change_percentage_24h": 0.0
                }

            except Exception as ex:
                app.logger.error(f"extra coin: {coin}; {ex}")

            try:
                # additional call to fetch 24h pct change
                url = f"{self._http_api_gecko}/coins/{coin}?tickers=false&market_data=true&community_data=false&developer_data=false&sparkline=false"
                blob = await httpget(url, json=True, timeout=15)
                obj["price_change_percentage_24h"] = blob.get("market_data", {}).get("price_change_percentage_24h")
            except:
                pass

            rates.append(obj)

        return rates
