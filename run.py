# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2020, The Monero Project.
# Copyright (c) 2020, dsc@xmr.pm

from wowlet_backend.factory import create_app
import settings

app = create_app()
app.run(settings.HOST, port=settings.PORT, debug=settings.DEBUG, use_reloader=False)
