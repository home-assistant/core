import asyncio

from afsapi import AFSAPI as AFSAPI_Original


class AFSAPI(AFSAPI_Original):
    # add additional API endpoints from https://github.com/zhelev/python-afsapi/pull/4
    API = dict(
        **AFSAPI_Original.API,
        **{
            # nav
            "nav": "netremote.nav.state",
            "preset": "netremote.nav.action.selectPreset",
        },
    )

    # Nav
    @asyncio.coroutine
    def set_preset(self, preset):
        """Select preset."""
        # enter nav mode
        nav = yield from self.handle_set(self.API.get("nav"), 1)
        if not nav:
            return False
        # select preset
        ok = yield from self.handle_set(self.API.get("preset"), preset)
        # leave nav mode
        nav = yield from self.handle_set(self.API.get("nav"), 0)

        return ok
