"""Tests for the DVLA data update coordinator through config entry setup."""

from unittest.mock import AsyncMock

from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.dvla.const import CONF_REG_NUMBER
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant


async def test_setup_entry_normalizes_registration_number(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_dvla_client: AsyncMock,
) -> None:
    """Test setup normalizes the registration number before fetching data."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        data={CONF_REG_NUMBER: "ab12 cde"},
    )

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_dvla_client.assert_awaited_once_with("AB12CDE")
