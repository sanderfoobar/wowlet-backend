# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2020, The Monero Project.
# Copyright (c) 2020, dsc@xmr.pm

import json
from typing import List

import settings
from wowlet_backend.utils import httpget, popularity_contest
from wowlet_backend.tasks import FeatherTask


class RPCNodeCheckTask(FeatherTask):
    def __init__(self, interval: int = 60):
        super(RPCNodeCheckTask, self).__init__(interval)

        self._cache_key = "rpc_nodes"
        self._cache_expiry = None

        self._websocket_cmd = "nodes"

        self._http_timeout = 5
        self._http_timeout_onion = 10

    async def task(self) -> List[dict]:
        """Check RPC nodes status"""
        from wowlet_backend.factory import app, cache

        try:
            heights = json.loads(await cache.get("blockheights"))
        except:
            heights = {}

        rpc_nodes = await self.cache_json_get("nodes")

        nodes = []
        for network_type_coin, _ in rpc_nodes.items():
            data = []

            for network_type, _nodes in _.items():
                for node in _nodes:
                    try:
                        blob = await self.node_check(node, network_type=network_type)
                        data.append(blob)
                    except Exception as ex:
                        app.logger.warning(f"node {node} not reachable; {ex}")
                        data.append(self._bad_node({
                            "address": node,
                            "nettype": network_type_coin,
                            "type": network_type,
                            "height": 0
                        }, reason="unreachable"))

            # not neccesary for stagenet/testnet nodes to be validated
            if network_type_coin != "mainnet":
                nodes += data
                continue

            if not data:
                continue

            # Filter out nodes affected by < v0.17.1.3 sybil attack
            data = list(map(lambda _node: _node if _node['target_height'] <= _node['height']
                            else self._bad_node(_node, reason="+2_attack"), data))

            allowed_offset = 3
            valid_heights = []
            # current_blockheight = heights.get(network_type_coin, 0)

            # popularity contest
            common_height = popularity_contest([z['height'] for z in data if z['height'] != 0])
            valid_heights = range(common_height + allowed_offset, common_height - allowed_offset, -1)

            data = list(map(lambda _node: _node if _node['height'] in valid_heights
                            else self._bad_node(_node, reason="out_of_sync"), data))
            nodes += data
        return nodes

    async def node_check(self, node, network_type: str) -> dict:
        """Call /get_info on the RPC, return JSON"""
        opts = {
            "timeout": self._http_timeout,
            "json": True
        }

        if network_type == "tor":
            opts["socks5"] = settings.TOR_SOCKS_PROXY
            opts["timeout"] = self._http_timeout_onion

        blob = await httpget(f"http://{node}/get_info", **opts)
        for expect in ["nettype", "height", "target_height"]:
            if expect not in blob:
                raise Exception(f"Invalid JSON response from RPC; expected key '{expect}'")

        height = int(blob.get("height", 0))
        target_height = int(blob.get("target_height", 0))

        return {
            "address": node,
            "height": height,
            "target_height": target_height,
            "online": True,
            "nettype": blob["nettype"],
            "type": network_type
        }

    def _bad_node(self, node: dict, reason=""):
        return {
            "address": node['address'],
            "height": node['height'],
            "target_height": 0,
            "online": False,
            "nettype": node['nettype'],
            "type": node['type'],
            "reason": reason
        }
