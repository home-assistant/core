"""Tests for the Kodi integration."""
from homeassistant.components.kodi.const import DOMAIN
from homeassistant.const import CONF_HOST

from .util import MockConnection

from tests.async_mock import patch
from tests.common import MockConfigEntry


async def init_integration(hass) -> MockConfigEntry:
    """Set up the Kodi integration in Home Assistant."""
    entry_data = {
        CONF_HOST: "1.1.1.1",
    }
    entry = MockConfigEntry(domain=DOMAIN, data=entry_data)
    with patch(
        "homeassistant.components.kodi.Kodi.ping",
        return_value=True,
    ), patch(
        "homeassistant.components.kodi.Kodi.get_application_properties",
        return_value={"version": {"major": 1, "minor": 1}},
    ), patch(
        "homeassistant.components.kodi.get_kodi_connection",
        return_value=MockConnection(),
    ):
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry
