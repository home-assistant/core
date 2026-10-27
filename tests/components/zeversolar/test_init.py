"""Test the init file code."""

from unittest.mock import MagicMock, patch

from pytest_homeassistant.common import MockConfigEntry
from zeversolar.exceptions import ZeverSolarTimeout

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant


async def test_async_setup_entry_fails(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_zeversolar_client: MagicMock,
) -> None:
    """Test to load/unload the integration."""
    config_entry.add_to_hass(hass)

    mock_zeversolar_client.get_data.side_effect = ZeverSolarTimeout
    await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.SETUP_RETRY

    mock_zeversolar_client.get_data.side_effect = None
    with patch("homeassistant.components.zeversolar.PLATFORMS", []):
        hass.config_entries.async_schedule_reload(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.LOADED

    with patch("homeassistant.components.zeversolar.PLATFORMS", []):
        result = await hass.config_entries.async_unload(config_entry.entry_id)
    assert result is True
    assert config_entry.state is ConfigEntryState.NOT_LOADED
