"""Test helpers for the Sure Petcare integration."""

from homeassistant.components.surepetcare.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_TOKEN, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def help_setup_mock_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Help setting up a mocked config entry."""
    data = {
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "test-password",
        CONF_TOKEN: "token",
        "feeders": [12345],
        "flaps": [13579, 13576],
        "pets": [24680],
    }
    entry = MockConfigEntry(domain=DOMAIN, data=data)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    return entry
