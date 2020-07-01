"""Tests for the WLED integration."""

import json

from homeassistant.components.wled.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_MAC
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_fixture
from tests.test_util.aiohttp import AiohttpClientMocker


async def init_integration(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    rgbw: bool = False,
    skip_setup: bool = False,
) -> MockConfigEntry:
    """Set up the WLED integration in Home Assistant."""

    fixture = "wled/rgb.json" if not rgbw else "wled/rgbw.json"
    data = json.loads(load_fixture(fixture))

    aioclient_mock.get(
        "http://192.168.1.123:80/json/",
        json=data,
        headers={"Content-Type": "application/json"},
    )

    aioclient_mock.post(
        "http://192.168.1.123:80/json/state",
        json=data["state"],
        headers={"Content-Type": "application/json"},
    )

    aioclient_mock.get(
        "http://192.168.1.123:80/json/info",
        json=data["info"],
        headers={"Content-Type": "application/json"},
    )

    aioclient_mock.get(
        "http://192.168.1.123:80/json/state",
        json=data["state"],
        headers={"Content-Type": "application/json"},
    )

    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "192.168.1.123", CONF_MAC: "aabbccddeeff"}
    )

    entry.add_to_hass(hass)

    if not skip_setup:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry
