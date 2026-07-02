"""Tests for the Picnic coordinator."""

from unittest.mock import MagicMock

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_timeout_failed_with_retry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_picnic_api: MagicMock,
) -> None:
    """Test that a TimeoutError is handled properly."""
    mock_picnic_api.get_cart.side_effect = TimeoutError

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
