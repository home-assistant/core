"""Test the APSystem setup."""

from unittest.mock import AsyncMock

from APsystemsEZ1 import InverterReturnedError

from homeassistant.components.apsystems.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


async def test_update_failed(
    hass: HomeAssistant,
    mock_apsystems: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test update failed."""
    mock_apsystems.get_output_data.side_effect = InverterReturnedError
    await setup_integration(hass, mock_config_entry)
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.state is ConfigEntryState.SETUP_RETRY
