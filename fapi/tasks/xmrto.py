# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2020, The Monero Project.
# Copyright (c) 2020, dsc@xmr.pm

import settings
from fapi.utils import httpget
from fapi.tasks import FeatherTask


class XmrToTask(FeatherTask):
    def __init__(self, interval: int = 30):
        super(XmrToTask, self).__init__(interval)

        self._cache_key = "xmrto_rates"
        self._cache_expiry = self.interval * 10

        if settings.COIN_MODE == 'stagenet':
            self._http_endpoint = "https://test.xmr.to/api/v3/xmr2btc/order_parameter_query/"
        else:
            self._http_endpoint = "https://xmr.to/api/v3/xmr2btc/order_parameter_query/"

    async def task(self):
        result = await httpget(self._http_endpoint)
        if "error" in result:
            raise Exception(f"${result['error']} ${result['error_msg']}")
        return result
