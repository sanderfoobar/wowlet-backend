# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2020, The Monero Project.
# Copyright (c) 2020, dsc@xmr.pm

import json
import asyncio

from quart import Quart
from quart_session import Session
import aioredis

import settings

app = None
cache = None
connected_websockets = set()
api_data = {}
user_agents = None
txfiatdb = None

print("""\033[91m
  █████▒▓█████ ▄▄▄     ▄▄▄█████▓ ██░ ██ ▓█████  ██▀███  
▓██   ▒ ▓█   ▀▒████▄   ▓  ██▒ ▓▒▓██░ ██▒▓█   ▀ ▓██ ▒ ██▒
▒████ ░ ▒███  ▒██  ▀█▄ ▒ ▓██░ ▒░▒██▀▀██░▒███   ▓██ ░▄█ ▒
░▓█▒  ░ ▒▓█  ▄░██▄▄▄▄██░ ▓██▓ ░ ░▓█ ░██ ▒▓█  ▄ ▒██▀▀█▄  
░▒█░    ░▒████▒▓█   ▓██▒ ▒██▒ ░ ░▓█▒░██▓░▒████▒░██▓ ▒██▒
 ▒ ░    ░░ ▒░ ░▒▒   ▓▒█░ ▒ ░░    ▒ ░░▒░▒░░ ▒░ ░░ ▒▓ ░▒▓░
 ░       ░ ░  ░ ▒   ▒▒ ░   ░     ▒ ░▒░ ░ ░ ░  ░  ░▒ ░ ▒░
 ░ ░       ░    ░   ▒    ░       ░  ░░ ░   ░     ░░   ░ 
           ░  ░     ░  ░         ░  ░  ░   ░  ░   ░     \033[0m
""".strip())


async def _setup_cache(app: Quart):
    global cache
    data = {
        "address": settings.redis_address
    }

    if settings.redis_password:
        data['password'] = settings.redis_password

    cache = await aioredis.create_redis_pool(**data)
    app.config['SESSION_TYPE'] = 'redis'
    app.config['SESSION_REDIS'] = cache
    Session(app)


def create_app():
    global app
    app = Quart(__name__)

    @app.before_serving
    async def startup():
        global txfiatdb, user_agents
        await _setup_cache(app)
        loop = asyncio.get_event_loop()

        with open('data/nodes.json', 'r') as f:
            nodes = json.loads(f.read())
            cache.execute('JSON.SET', 'nodes', '.', json.dumps(nodes))

        with open('data/user_agents.txt', 'r') as f:
            user_agents = [l.strip() for l in f.readlines() if l.strip()]

        from fapi.fapi import FeatherApi
        from fapi.utils import loopyloop, TxFiatDb, XmrRig
        txfiatdb = TxFiatDb(settings.crypto_name, settings.crypto_block_date_start)
        loop.create_task(loopyloop(20, FeatherApi.xmrto_rates, FeatherApi.after_xmrto))
        loop.create_task(loopyloop(120, FeatherApi.crypto_rates, FeatherApi.after_crypto))
        loop.create_task(loopyloop(600, FeatherApi.fiat_rates, FeatherApi.after_fiat))
        loop.create_task(loopyloop(300, FeatherApi.ccs, FeatherApi.after_ccs))
        loop.create_task(loopyloop(900, FeatherApi.reddit, FeatherApi.after_reddit))
        loop.create_task(loopyloop(60, FeatherApi.blockheight, FeatherApi.after_blockheight))
        loop.create_task(loopyloop(60, FeatherApi.check_nodes, FeatherApi.after_check_nodes))
        loop.create_task(loopyloop(43200, txfiatdb.update))
        loop.create_task(loopyloop(43200, XmrRig.releases, XmrRig.after_releases))
        import fapi.routes

    return app
