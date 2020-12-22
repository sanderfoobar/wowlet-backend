# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2020, The Monero Project.
# Copyright (c) 2020, dsc@xmr.pm

from fapi.utils import httpget
from fapi.tasks import FeatherTask


class FiatRatesTask(FeatherTask):
    def __init__(self, interval: int = 600):
        super(FiatRatesTask, self).__init__(interval)

        self._cache_key = "fiat_rates"
        self._cache_expiry = self.interval * 10

        self._websocket_cmd = "fiat_rates"

        self._http_endpoint = "https://api.exchangeratesapi.io/latest?base=USD"

    async def task(self):
        """Fetch fiat rates"""
        result = await httpget(self._http_endpoint, json=True)
        return result
