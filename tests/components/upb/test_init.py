"""The init tests for the UPB platform."""

from unittest.mock import patch

from homeassistant.components.upb.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_migrate_entry_minor_version_1_3(hass: HomeAssistant) -> None:
    """Test migrating a 1.1 config entry to 1.3."""
    with patch("homeassistant.components.upb.async_setup_entry", return_value=True):
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={"host": "tcp://1.2.3.4", "file_path": "upb.upe"},
            version=1,
            minor_version=1,
            unique_id=123456,
        )
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        assert entry.version == 1
        assert entry.minor_version == 3
        assert entry.unique_id == "123456"
        assert entry.data == {"device": "tcp://1.2.3.4", "file_path": "upb.upe"}


async def test_migrate_entry_minor_version_2_3(hass: HomeAssistant) -> None:
    """Test migrating a 1.2 config entry to 1.3."""
    with patch("homeassistant.components.upb.async_setup_entry", return_value=True):
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={"host": "serial:///dev/ttyS0", "file_path": "upb.upe"},
            version=1,
            minor_version=2,
            unique_id="42",
        )
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        assert entry.version == 1
        assert entry.minor_version == 3
        assert entry.data == {"device": "serial:///dev/ttyS0", "file_path": "upb.upe"}
