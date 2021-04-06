# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2020, The Monero Project.
# Copyright (c) 2020, dsc@xmr.pm

import json
import asyncio
from typing import List, Set
from datetime import datetime

from quart import Quart
from quart_session import Session
import aioredis

from wowlet_backend.utils import current_worker_thread_is_primary, print_banner
import settings

now = datetime.now()
app: Quart = None
cache = None
user_agents: List[str] = None
connected_websockets: Set[asyncio.Queue] = set()
_is_primary_worker_thread = False


async def _setup_nodes(app: Quart):
    global cache
    with open('data/nodes.json', 'r') as f:
        nodes = json.loads(f.read()).get(settings.COIN_SYMBOL)
        await cache.set('nodes', json.dumps(nodes).encode())


async def _setup_user_agents(app: Quart):
    global user_agents
    with open('data/user_agents.txt', 'r') as f:
        user_agents = [l.strip() for l in f.readlines() if l.strip()]


async def _setup_cache(app: Quart):
    global cache
    # Each coin has it's own Redis DB index; `redis-cli -n $INDEX`
    db = {"xmr": 0, "wow": 1, "aeon": 2, "trtl": 3, "msr": 4, "xhv": 5, "loki": 6}[settings.COIN_SYMBOL]
    data = {
        "address": settings.REDIS_ADDRESS,
        "db": db,
        "password": settings.REDIS_PASSWORD if settings.REDIS_PASSWORD else None
    }

    cache = await aioredis.create_redis_pool(**data)
    app.config['SESSION_TYPE'] = 'redis'
    app.config['SESSION_REDIS'] = cache
    Session(app)


async def _setup_tasks(app: Quart):
    """Schedules a series of tasks at an interval."""
    if not _is_primary_worker_thread:
        return

    from wowlet_backend.tasks import (
        BlockheightTask, HistoricalPriceTask, FundingProposalsTask,
        CryptoRatesTask, FiatRatesTask, RedditTask, RPCNodeCheckTask,
        XmrigTask, SuchWowTask)

    asyncio.create_task(BlockheightTask().start())
    asyncio.create_task(HistoricalPriceTask().start())
    asyncio.create_task(CryptoRatesTask().start())
    asyncio.create_task(FiatRatesTask().start())
    asyncio.create_task(RedditTask().start())
    asyncio.create_task(RPCNodeCheckTask().start())
    asyncio.create_task(XmrigTask().start())
    asyncio.create_task(SuchWowTask().start())

    if settings.COIN_SYMBOL in ["xmr", "wow"]:
        asyncio.create_task(FundingProposalsTask().start())


def _setup_logging():
    from logging import Formatter
    from logging.config import dictConfig
    from quart.logging import default_handler
    default_handler.setFormatter(Formatter('[%(asctime)s] %(levelname)s in %(funcName)s(): %(message)s (%(pathname)s)'))

    dictConfig({
        'version': 1,
        'loggers': {
            'quart.app': {
                'level': 'DEBUG' if settings.DEBUG else 'INFO',
            },
        },
    })


def create_app():
    global app

    _setup_logging()
    app = Quart(__name__)

    @app.before_serving
    async def startup():
        global _is_primary_worker_thread
        _is_primary_worker_thread = current_worker_thread_is_primary()

        if _is_primary_worker_thread:
            print_banner()

        await _setup_cache(app)
        await _setup_nodes(app)
        await _setup_user_agents(app)
        await _setup_tasks(app)

        import wowlet_backend.routes

    return app
