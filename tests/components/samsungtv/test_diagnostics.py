"""Test samsungtv diagnostics."""
from aiohttp import ClientSession
import pytest

from homeassistant.components.diagnostics import REDACTED
from homeassistant.components.samsungtv import DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .test_media_player import MOCK_ENTRY_WS_WITH_MAC

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry


@pytest.fixture(name="config_entry")
def get_config_entry(hass: HomeAssistant) -> ConfigEntry:
    """Create and register mock config entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_ENTRY_WS_WITH_MAC,
        entry_id="123456",
        unique_id="any",
    )
    config_entry.add_to_hass(hass)
    return config_entry


@pytest.mark.usefixtures("remotews")
async def test_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry, hass_client: ClientSession
) -> None:
    """Test config entry diagnostics."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert await get_diagnostics_for_config_entry(hass, hass_client, config_entry) == {
        "entry": {
            "data": {
                "host": "fake_host",
                "ip_address": "test",
                "mac": "aa:bb:cc:dd:ee:ff",
                "method": "websocket",
                "model": "82GXARRS",
                "name": "fake",
                "port": 8002,
                "token": REDACTED,
            },
            "disabled_by": None,
            "domain": "samsungtv",
            "entry_id": "123456",
            "options": {},
            "pref_disable_new_entities": False,
            "pref_disable_polling": False,
            "source": "user",
            "title": "Mock Title",
            "unique_id": "any",
            "version": 2,
        },
        "device_info": {
            "id": "uuid:be9554b9-c9fb-41f4-8920-22da015376a4",
            "device": {
                "modelName": "82GXARRS",
                "name": "[TV] Living Room",
                "networkType": "wireless",
                "type": "Samsung SmartTV",
                "wifiMac": "aa:bb:cc:dd:ee:ff",
            },
        },
    }
