import asyncio

from afsapi import AFSAPI as AFSAPI_Original


class AFSAPI(AFSAPI_Original):
    # add additional API endpoints from https://github.com/zhelev/python-afsapi/pull/4
    API = dict(
        **AFSAPI_Original.API,
        **{
            # nav
            "nav": "netremote.nav.state",
            "presets": "netRemote.nav.presets",
            "select_preset": "netremote.nav.action.selectPreset",
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
        ok = yield from self.handle_set(self.API.get("select_preset"), preset)
        # leave nav mode
        nav = yield from self.handle_set(self.API.get("nav"), 0)

        return ok

    @asyncio.coroutine
    def get_presets(self):
        """Get the channel presets from the device."""
        # enter nav mode
        nav = yield from self.handle_set(self.API.get("nav"), 1)
        if not nav:
            return False
        # get list of presets
        presets = yield from self.handle_list(self.API.get("presets"))
        # leave nav mode
        nav = yield from self.handle_set(self.API.get("nav"), 0)

        results = []
        for preset in presets:
            if "name" in preset and preset["name"].text:
                results.append({**preset, **{"label": preset["name"].text.strip()}})

        return results

    @asyncio.coroutine
    def get_preset_list(self):
        """Get the label list of presets."""
        presets = yield from self.get_presets()
        return (yield from self.collect_labels(presets))
