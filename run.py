# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2020, The Monero Project.
# Copyright (c) 2020, dsc@xmr.pm

from fapi.factory import create_app
import settings

app = create_app()
app.run(settings.host, port=settings.port, debug=settings.debug, use_reloader=False)
