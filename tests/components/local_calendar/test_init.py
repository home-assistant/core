"""Tests for init platform of local calendar."""

from unittest.mock import patch

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_remove_config_entry(
    hass: HomeAssistant, setup_integration: None, config_entry: MockConfigEntry
) -> None:
    """Test removing a config entry."""

    with patch("homeassistant.components.local_calendar.Path.unlink") as unlink_mock:
        assert await hass.config_entries.async_remove(config_entry.entry_id)
        await hass.async_block_till_done()
        unlink_mock.assert_called_once()
