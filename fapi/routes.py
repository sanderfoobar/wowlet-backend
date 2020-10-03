# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2020, The Monero Project.
# Copyright (c) 2020, dsc@xmr.pm

import asyncio
import json
from copy import deepcopy

from quart import websocket, jsonify

from fapi.factory import app
from fapi.wsparse import WebsocketParse
from fapi.utils import collect_websocket


@app.route("/")
async def root():
    from fapi.factory import api_data
    return jsonify(api_data)


@app.websocket('/ws')
@collect_websocket
async def ws(queue):
    from fapi.factory import api_data

    # blast data on connect
    _api_data = deepcopy(api_data)  # prevent race condition
    for k, v in _api_data.items():
        if not v:
            continue
        await websocket.send(json.dumps({"cmd": k, "data": v}).encode())
    _api_data = None

    async def rx():
        while True:
            data = await websocket.receive()
            try:
                blob = json.loads(data)
                if "cmd" not in blob:
                    continue
                cmd = blob.get('cmd')
                _data = blob.get('data')
                result = await WebsocketParse.parser(cmd, _data)
                if result:
                    rtn = json.dumps({"cmd": cmd, "data": result}).encode()
                    await websocket.send(rtn)
            except Exception as ex:
                continue

    async def tx():
        while True:
            data = await queue.get()
            payload = json.dumps(data).encode()
            await websocket.send(payload)

    # bidirectional async rx and tx loops
    consumer_task = asyncio.ensure_future(rx())
    producer_task = asyncio.ensure_future(tx())
    try:
        await asyncio.gather(consumer_task, producer_task)
    finally:
        consumer_task.cancel()
        producer_task.cancel()


@app.errorhandler(403)
@app.errorhandler(404)
@app.errorhandler(405)
@app.errorhandler(500)
def page_not_found(e):
    return ":)", 500
