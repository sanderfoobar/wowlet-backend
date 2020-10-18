# feather-ws

This is the back-end websocket server for Feather wallet.

- Python 3 asyncio
- Quart web framework
- Redis


### Supervisor

Example config.

```text
[program:ws]
directory=/home/feather/feather-ws
command=/home/feather/feather-ws/venv/bin/python run.py
autostart=true
autorestart=true
startsecs=6
stdout_logfile=/home/feather/feather-ws/stdout.log
stdout_logfile_maxbytes=1MB
stdout_logfile_backups=10
stdout_capture_maxbytes=1MB
stderr_logfile=/home/feather/feather-ws/stderr.log
stderr_logfile_maxbytes=1MB
stderr_logfile_backups=10
stderr_capture_maxbytes=1MB
user = feather
environment=
    HOME="/home/feather",
    USER="feather",
    PATH="/home/feather/feather-ws/venv/bin"
```
