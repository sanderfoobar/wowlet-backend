# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2020, The Monero Project.
# Copyright (c) 2020, dsc@xmr.pm

from bs4 import BeautifulSoup
from typing import List

import settings
from wowlet_backend.utils import httpget
from wowlet_backend.tasks import FeatherTask


class FundingProposalsTask(FeatherTask):
    """Fetch funding proposals made by the community."""
    def __init__(self, interval: int = 600):
        from wowlet_backend.factory import app
        super(FundingProposalsTask, self).__init__(interval)

        self._cache_key = "funding_proposals"
        self._cache_expiry = self.interval * 1000

        # url
        self._http_endpoints = {
            "xmr": "https://ccs.getmonero.org",
            "wow": "https://funding.wownero.com"
        }

        if settings.COIN_SYMBOL not in self._http_endpoints:
            app.logger.warning(f"Missing proposal URL for {settings.COIN_SYMBOL.upper()}, ignoring update task")
            self._active = False

        self._http_endpoint = self._http_endpoints[settings.COIN_SYMBOL]
        if self._http_endpoint.endswith("/"):
            self._http_endpoint = self._http_endpoint[:-1]

        # websocket
        self._websocket_cmd = "funding_proposals"
        self._websocket_cmds = {
            "xmr": "ccs",
            "wow": "wfs"
        }

        if settings.COIN_SYMBOL not in self._websocket_cmds:
            app.logger.warning(f"Missing websocket cmd for {settings.COIN_SYMBOL.upper()}, ignoring update task")
            self._active = False

        self._websocket_cmd = self._websocket_cmds[settings.COIN_SYMBOL]

    async def task(self):
        if settings.COIN_SYMBOL == "xmr":
            return await self._xmr()
        elif settings.COIN_SYMBOL == "wow":
            return await self._wfs()

    async def _xmr(self) -> List[dict]:
        # CCS API is lacking;
        # - API returns more `FUNDING-REQUIRED` proposals than there are on the website
        # - API does not allow filtering
        # - API sometimes breaks; https://hackerone.com/reports/934231
        # we'll web scrape instead
        from wowlet_backend.factory import app

        content = await httpget(f"{self._http_endpoint}/funding-required/", json=False)
        soup = BeautifulSoup(content, "html.parser")

        listings = []
        for listing in soup.findAll("a", {"class": "ffs-idea"}):
            try:
                item = {
                    "state": "FUNDING-REQUIRED",
                    "author": listing.find("p", {"class": "author-list"}).text,
                    "date": listing.find("p", {"class": "date-list"}).text,
                    "title": listing.find("h3").text,
                    "raised_amount": float(listing.find("span", {"class": "progress-number-funded"}).text),
                    "target_amount": float(listing.find("span", {"class": "progress-number-goal"}).text),
                    "contributors": 0,
                    "url": f"{self._http_endpoint}{listing.attrs['href']}"
                }
                item["percentage_funded"] = item["raised_amount"] * (100 / item["target_amount"])
                if item["percentage_funded"] >= 100:
                    item["percentage_funded"] = 100.0
                try:
                    item["contributors"] = int(listing.find("p", {"class": "contributor"}).text.split(" ")[0])
                except:
                    pass

                href = listing.attrs['href']

                try:
                    content = await httpget(f"{self._http_endpoint}{href}", json=False)
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
                listings.append(item)
            except Exception as ex:
                app.logger.error(f"error parsing a ccs item: {ex}")

        return listings

    async def _wfs(self) -> List[dict]:
        """https://git.wownero.com/wownero/wownero-funding-system"""
        blob = await httpget(f"{self._http_endpoint}/api/1/proposals?offset=0&limit=10&status=2", json=True)
        if "data" not in blob:
            raise Exception("invalid json response")

        listings = []
        for p in blob['data']:
            item = {
                "address": p["addr_donation"],
                "url": f"{self._http_endpoint}/proposal/{p['id']}",
                "state": "FUNDING-REQUIRED",
                "date": p['date_posted'],
                "title": p['headline'],
                'target_amount': p['funds_target'],
                'raised_amount': round(p['funds_target'] / 100 * p['funded_pct'], 2),
                'contributors': 0,
                'percentage_funded': round(p['funded_pct'], 2),
                'author': p['user']
            }
            listings.append(item)
        return listings
