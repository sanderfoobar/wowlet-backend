# feather-ws

Back-end websocket server for Feather wallet.

- Quart web framework, Py3 asyncio
- Redis

## Coins supported

- Monero
- Wownero

See also the environment variables `FEATHER_COIN_NAME`, `FEATHER_COIN_SYMBOL`, etc. in `settings.py`.

## Tasks

This websocket server has several scheduled recurring tasks:

- Fetch latest blockheight from various block explorers
- Fetch crypto/fiat exchange rates
- Fetch latest Reddit posts
- Fetch funding proposals
- Check status of RPC nodes (`data/nodes.json`)

When Feather wallet starts up, it will connect to
this websocket server and receive the information
listed above which is necessary for normal operation.

See `fapi.tasks.*` for the various tasks.

## Development

Requires Python 3.7 and higher.

```
virtualenv -p /usr/bin/python3 venv
source venv/bin/activate
pip install -r requirements.txt

export FEATHER_DEBUG=true
python run.py
```

Note that `run.py` is meant as a development server. For production,
use `asgi.py` with something like hypercorn.

## Docker

In production you may run via docker;

```
docker-compose up
```

Will bind on `http://127.0.0.1:1337`. Modify `docker-compose.yml` if necessary.
