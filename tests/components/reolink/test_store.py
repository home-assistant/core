"""Test the Reolink store."""

from unittest.mock import MagicMock

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_privacy_mode_store_no_file(
    hass: HomeAssistant,
    reolink_connect: MagicMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test loading reolink file when the file does not exists."""
    reolink_connect.baichuan.privacy_mode.return_value = True
    reolink_connect.path_mock.exists.return_value = False

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state == ConfigEntryState.LOADED
    reolink_connect.baichuan.privacy_mode.return_value = False
    reolink_connect.path_mock.exists.return_value = True


async def test_privacy_mode_store_OSError(
    hass: HomeAssistant,
    reolink_connect: MagicMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test loading reolink file when a OSError occurs."""
    reolink_connect.baichuan.privacy_mode.return_value = True
    reolink_connect.path_mock.read_text.side_effect = OSError("Test Error")

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state == ConfigEntryState.LOADED
    reolink_connect.baichuan.privacy_mode.return_value = False
    reolink_connect.path_mock.read_text.reset_mock(side_effect=True)
