# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2020, The Monero Project.
# Copyright (c) 2020, dsc@xmr.pm

import json

import aiohttp
from bs4 import BeautifulSoup
from aiohttp_socks import ProxyType, ProxyConnector, ChainProxyConnector
from fapi.utils import broadcast_blockheight, broadcast_nodes, httpget, BlockHeight

import settings


class FeatherApi:
    @staticmethod
    async def redis_get(key):
        from fapi.factory import app, cache
        try:
            data = await cache.get(key)
            if data:
                return json.loads(data)
        except Exception as ex:
            app.logger.error(f"Redis error: {ex}")

    @staticmethod
    async def xmrto_rates():
        from fapi.factory import app, cache
        xmrto_rates = await FeatherApi.redis_get("xmrto_rates")
        if xmrto_rates and app.config["DEBUG"]:
            return xmrto_rates

        try:
            result = await httpget(settings.urls["xmrto_rates"])
            if not result:
                raise Exception("empty response")
            if "error" in result:
                raise Exception(f"${result['error']} ${result['error_msg']}")
            return result
        except Exception as ex:
            app.logger.error(f"error parsing xmrto_rates blob: {ex}")
        return xmrto_rates

    @staticmethod
    async def after_xmrto(data):
        from fapi.factory import app, cache, api_data, connected_websockets
        if not data:
            return

        _data = api_data.get("xmrto_rates", {})
        _data = json.dumps(_data, sort_keys=True, indent=4)
        if json.dumps(data, sort_keys=True, indent=4) == _data:
            return

        api_data["xmrto_rates"] = data

    @staticmethod
    async def crypto_rates():
        from fapi.factory import app, cache
        crypto_rates = await FeatherApi.redis_get("crypto_rates")
        if crypto_rates and app.config["DEBUG"]:
            return crypto_rates

        result = None
        try:
            result = await httpget(settings.urls["crypto_rates"])
            if not result:
                raise Exception("empty response")
            crypto_rates = result
        except Exception as ex:
            app.logger.error(f"error parsing crypto_rates blob: {ex}")

        if not result and crypto_rates:
            app.logger.warning("USING OLD CACHE FOR CRYPTO RATES")
            return crypto_rates

        # grab WOW price while we're at it...

        try:
            _result = await httpget(settings.urls["crypto_wow_rates"])
            if not _result:
                raise Exception("empty response")
        except Exception as ex:
            _result = {}
        if "wownero" in _result and "usd" in _result["wownero"]:
            crypto_rates.append({
                "id": "wownero",
                "symbol": "wow",
                "image": "",
                "name": "Wownero",
                "current_price": _result["wownero"]["usd"],
                "price_change_percentage_24h": 0.0
            })

        await cache.set("crypto_rates", json.dumps(crypto_rates))
        return crypto_rates

    @staticmethod
    async def after_crypto(data):
        from fapi.factory import app, cache, api_data, connected_websockets
        if not data:
            return

        _data = api_data.get("crypto_rates", {})
        _data = json.dumps(_data, sort_keys=True, indent=4)
        if json.dumps(data, sort_keys=True, indent=4) == _data:
            return

        _data = []
        for obj in data:
            _data.append({
                "id": obj['id'],
                "symbol": obj['symbol'],
                "image": obj['image'],
                "name": obj['name'],
                "current_price": obj['current_price'],
                "price_change_percentage_24h": obj['price_change_percentage_24h']
            })

        api_data["crypto_rates"] = data
        for queue in connected_websockets:
            await queue.put({
                "cmd": "crypto_rates",
                "data": {
                    "crypto_rates": api_data["crypto_rates"]
                }
            })

    @staticmethod
    async def fiat_rates():
        from fapi.factory import app, cache
        fiat_rates = await FeatherApi.redis_get("fiat_rates")
        if fiat_rates and app.config["DEBUG"]:
            return fiat_rates

        try:
            result = await httpget(settings.urls["fiat_rates"], json=True)
            if not result:
                raise Exception("empty response")
            await cache.set("fiat_rates", json.dumps(result))
            return result
        except Exception as ex:
            app.logger.error(f"error parsing fiat_rates blob: {ex}")

        # old cache
        app.logger.warning("USING OLD CACHE FOR FIAT RATES")
        return fiat_rates

    @staticmethod
    async def after_fiat(data):
        from fapi.factory import app, cache, api_data, connected_websockets
        if not data:
            return

        _data = api_data.get("fiat_rates", {})
        _data = json.dumps(_data, sort_keys=True, indent=4)
        if json.dumps(data, sort_keys=True, indent=4) == _data:
            return

        api_data["fiat_rates"] = data
        for queue in connected_websockets:
            await queue.put({
                "cmd": "fiat_rates",
                "data": {
                    "fiat_rates": api_data["fiat_rates"]
                }
            })

    @staticmethod
    async def ccs():
        # CCS JSON api is broken ;x https://hackerone.com/reports/934231
        from fapi.factory import app, cache
        ccs = await FeatherApi.redis_get("ccs")
        if ccs and app.config["DEBUG"]:
            return ccs

        try:
            content = await httpget(f"{settings.urls['ccs']}/funding-required/", json=False)
        except Exception as ex:
            app.logger.error(f"error fetching ccs HTML: {ex}")
            return ccs

        try:
            soup = BeautifulSoup(content, "html.parser")
        except Exception as ex:
            app.logger.error(f"error parsing ccs HTML page: {ex}")
            return ccs

        data = []
        for x in soup.findAll("a", {"class": "ffs-idea"}):
            try:
                item = {
                    "state": "FUNDING-REQUIRED",
                    "author": x.find("p", {"class": "author-list"}).text,
                    "date": x.find("p", {"class": "date-list"}).text,
                    "title": x.find("h3").text,
                    "raised_amount": float(x.find("span", {"class": "progress-number-funded"}).text),
                    "target_amount": float(x.find("span", {"class": "progress-number-goal"}).text),
                    "contributors": 0,
                    "url": f"https://ccs.getmonero.org{x.attrs['href']}"
                }
                item["percentage_funded"] = item["raised_amount"] * (100 / item["target_amount"])
                if item["percentage_funded"] >= 100:
                    item["percentage_funded"] = 100.0
                try:
                    item["contributors"] = int(x.find("p", {"class": "contributor"}).text.split(" ")[0])
                except:
                    pass

                href = x.attrs['href']

                try:
                    content = await httpget(f"{settings.urls['ccs']}{href}", json=False)
                    try:
                        soup2 = BeautifulSoup(content, "html.parser")
                    except Exception as ex:
                        app.logger.error(f"error parsing ccs HTML page: {ex}")
                        continue

                    try:
                        instructions = soup2.find("div", {"class": "instructions"})
                        if not instructions:
                            raise Exception("could not parse div.instructions, page probably broken")
                        address = instructions.find("p", {"class": "string"}).text
                        if not address.strip():
                            raise Exception(f"error fetching ccs HTML: could not parse address")
                        item["address"] = address.strip()
                    except Exception as ex:
                        app.logger.error(f"error parsing ccs address from HTML: {ex}")
                        continue
                except Exception as ex:
                    app.logger.error(f"error fetching ccs HTML: {ex}")
                    continue
                data.append(item)
            except Exception as ex:
                app.logger.error(f"error parsing a ccs item: {ex}")

        await cache.set("ccs", json.dumps(data))
        return data

    @staticmethod
    async def after_ccs(data):
        from fapi.factory import app, cache, api_data, connected_websockets
        if not data:
            return

        _data = api_data.get("ccs", {})
        _data = json.dumps(_data, sort_keys=True, indent=4)
        if json.dumps(data, sort_keys=True, indent=4) == _data:
            return

        api_data["ccs"] = data
        for queue in connected_websockets:
            await queue.put({
                "cmd": "ccs",
                "data": api_data["ccs"]
            })

    @staticmethod
    async def reddit():
        from fapi.factory import app, cache
        reddit = await FeatherApi.redis_get("reddit")
        if reddit and app.config["DEBUG"]:
            return reddit

        try:
            blob = await httpget(settings.urls["reddit"])
            if not blob:
                raise Exception("no data from url")
            blob = [{
                'title': z['data']['title'],
                'author': z['data']['author'],
                'url': "https://old.reddit.com" + z['data']['permalink'],
                'comments': z['data']['num_comments']
            } for z in blob['data']['children']]

            # success
            if blob:
                await cache.set("reddit", json.dumps(blob))
                return blob
        except Exception as ex:
            app.logger.error(f"error parsing reddit blob: {ex}")

        # old cache
        return reddit

    @staticmethod
    async def after_reddit(data):
        from fapi.factory import app, cache, api_data, connected_websockets
        if not data:
            return

        _data = api_data.get("reddit", {})
        _data = json.dumps(_data, sort_keys=True, indent=4)
        if json.dumps(data, sort_keys=True, indent=4) == _data:
            return

        api_data["reddit"] = data
        for queue in connected_websockets:
            await queue.put({
                "cmd": "reddit",
                "data": api_data["reddit"]
            })

    @staticmethod
    async def blockheight():
        from fapi.factory import app, cache
        data = {"mainnet": 0, "stagenet": 0}

        for stagenet in [False, True]:
            try:
                data["mainnet" if stagenet is False else "stagenet"] = \
                    await BlockHeight.xmrchain(stagenet)
            except Exception as ex:
                app.logger.error(f"Could not fetch blockheight from xmrchain")
                try:
                    data["mainnet" if stagenet is False else "stagenet"] = \
                        await BlockHeight.xmrto(stagenet)
                except:
                    app.logger.error(f"Could not fetch blockheight from xmr.to")
        return data

    @staticmethod
    async def after_blockheight(data):
        from fapi.factory import app, cache, api_data

        changed = False
        api_data.setdefault("blockheights", {})
        if data["mainnet"] > 1 and data["mainnet"] > api_data["blockheights"].get("mainnet", 1):
            api_data["blockheights"]["mainnet"] = data["mainnet"]
            changed = True
        if data["stagenet"] > 1 and data["stagenet"] > api_data["blockheights"].get("stagenet", 1):
            api_data["blockheights"]["stagenet"] = data["stagenet"]
            changed = True

        if changed:
            await broadcast_blockheight()

    @staticmethod
    async def check_nodes():
        from fapi.factory import nodes, app
        data = []
        for network_type, network_name in nodes.items():
            for k, _nodes in nodes[network_type].items():
                for node in _nodes:
                    timeout = aiohttp.ClientTimeout(total=5)
                    d = {'timeout': timeout}
                    if ".onion" in node:
                        d['connector'] = ProxyConnector.from_url(settings.tor_socks)
                        d['timeout'] = aiohttp.ClientTimeout(total=12)
                    try:
                        async with aiohttp.ClientSession(**d) as session:
                            async with session.get(f"http://{node}/get_info") as response:
                                blob = await response.json()
                                for expect in ["nettype", "height", "target_height"]:
                                    assert expect in blob
                                _node = {
                                    "address": node,
                                    "height": int(blob["height"]),
                                    "target_height": int(blob["target_height"]),
                                    "online": True,
                                    "nettype": blob["nettype"],
                                    "type": k
                                }
                    except Exception as ex:
                        app.logger.warning(f"node {node} not reachable")
                        _node = {
                            "address": node,
                            "height": 0,
                            "target_height": 0,
                            "online": False,
                            "nettype": network_type,
                            "type": k
                        }
                    data.append(_node)
        return data

    @staticmethod
    async def after_check_nodes(data):
        from fapi.factory import api_data
        api_data["nodes"] = data
        await broadcast_nodes()
