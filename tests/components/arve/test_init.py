"""Tests for the Arve component."""

from unittest.mock import patch

from homeassistant.components.arve.const import DOMAIN
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_CLIENT_SECRET
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_migrate_entry_minor_version_1_2(hass: HomeAssistant) -> None:
    """Test migrating a 1.1 config entry to 1.2."""
    with patch("homeassistant.components.arve.async_setup_entry", return_value=True):
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_ACCESS_TOKEN: "mock", CONF_CLIENT_SECRET: "mock"},
            version=1,
            minor_version=1,
            unique_id=12345,
        )
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        assert entry.version == 1
        assert entry.minor_version == 2
        assert entry.unique_id == "12345"
