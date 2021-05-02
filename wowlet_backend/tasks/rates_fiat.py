# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2020, The Monero Project.
# Copyright (c) 2020, dsc@xmr.pm

from datetime import datetime, timedelta
import re

from wowlet_backend.utils import httpget
from wowlet_backend.tasks import WowletTask


class FiatRatesTask(WowletTask):
    def __init__(self, interval: int = 43200):
        super(FiatRatesTask, self).__init__(interval)

        self._cache_key = "fiat_rates"
        self._cache_expiry = self.interval * 10

        self._websocket_cmd = "fiat_rates"

        self._http_endpoint = "https://sdw-wsrest.ecb.europa.eu/service/data/EXR/D.USD+GBP+JPY+CZK+CAD+ZAR+KRW+MXN+RUB+SEK+THB+NZD+AUD+CHF+TRY+CNY.EUR.SP00.A"

    async def task(self):
        """Fetch fiat rates"""
        start_from = "?startPeriod=" + (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        result = await httpget(self._http_endpoint + start_from, json=False)

        results = {}
        currency = ""
        value = ""

        # XML "parsing"
        for line in result.split("\n"):
            if "\"UNIT\"" in line:
                if currency:
                    results[currency] = value
                currency = re.search(r"value=\"(\w+)\"", line).group(1)
            if "ObsValue value" in line:
                value = float(re.search("ObsValue value=\"([0-9.]+)\"", line).group(1))

        # Base currency is EUR, needs to be USD
        results['EUR'] = 1
        usd_rate = results['USD']
        results = {k: round(v / usd_rate, 4) for k, v in results.items()}
        return results
