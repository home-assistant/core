"""Test the Devialet diagnostics."""

from pytest_homeassistant.common import async_load_json_object_fixture
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker
from pytest_homeassistant.typing import ClientSessionGenerator

from homeassistant.components.devialet.const import DOMAIN
from homeassistant.core import HomeAssistant

from . import setup_integration


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test diagnostics."""
    entry = await setup_integration(hass, aioclient_mock)

    assert await get_diagnostics_for_config_entry(hass, hass_client, entry) == {
        "is_available": True,
        "general_info": await async_load_json_object_fixture(
            hass, "general_info.json", DOMAIN
        ),
        "sources": await async_load_json_object_fixture(hass, "sources.json", DOMAIN),
        "source_state": await async_load_json_object_fixture(
            hass, "source_state.json", DOMAIN
        ),
        "volume": await async_load_json_object_fixture(hass, "volume.json", DOMAIN),
        "night_mode": await async_load_json_object_fixture(
            hass, "night_mode.json", DOMAIN
        ),
        "equalizer": await async_load_json_object_fixture(
            hass, "equalizer.json", DOMAIN
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
