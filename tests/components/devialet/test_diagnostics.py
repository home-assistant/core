"""Test the Devialet diagnostics."""

import json

from homeassistant.components.devialet.const import DOMAIN
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import async_load_fixture
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test diagnostics."""
    entry = await setup_integration(hass, aioclient_mock)

    assert await get_diagnostics_for_config_entry(hass, hass_client, entry) == {
        "is_available": True,
        "general_info": json.loads(
            await async_load_fixture(hass, "general_info.json", DOMAIN)
        ),
        "sources": json.loads(await async_load_fixture(hass, "sources.json", DOMAIN)),
        "source_state": json.loads(
            await async_load_fixture(hass, "source_state.json", DOMAIN)
        ),
        "volume": json.loads(await async_load_fixture(hass, "volume.json", DOMAIN)),
        "night_mode": json.loads(
            await async_load_fixture(hass, "night_mode.json", DOMAIN)
        ),
        "equalizer": json.loads(
            await async_load_fixture(hass, "equalizer.json", DOMAIN)
        ),
        "source_list": [
            "Airplay",
            "Bluetooth",
            "Optical left",
            "Optical right",
            "Raat",
            "Spotify Connect",
            "UPnP",
        ],
        "source": "spotifyconnect",
        "upnp_device_type": "Not available",
        "upnp_device_url": "Not available",
    }
