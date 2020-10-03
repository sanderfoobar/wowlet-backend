# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2020, The Monero Project.
# Copyright (c) 2020, dsc@xmr.pm


class WebsocketParse:
    @staticmethod
    async def parser(cmd: str, data=None):
        if cmd == "txFiatHistory":
            return await WebsocketParse.txFiatHistory(data)

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

        from fapi.factory import txfiatdb
        return txfiatdb.get(year, month)
