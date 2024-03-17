"""Test the Devialet diagnostics."""

import json

from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import load_fixture
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
        "general_info": json.loads(load_fixture("general_info.json", "devialet")),
        "sources": json.loads(load_fixture("sources.json", "devialet")),
        "source_state": json.loads(load_fixture("source_state.json", "devialet")),
        "volume": json.loads(load_fixture("volume.json", "devialet")),
        "night_mode": json.loads(load_fixture("night_mode.json", "devialet")),
        "equalizer": json.loads(load_fixture("equalizer.json", "devialet")),
        "source_list": [
            "Airplay",
            "Bluetooth",
            "Online",
            "Optical left",
            "Optical right",
            "Raat",
            "Spotify Connect",
        ],
        "source": "spotifyconnect",
    }
