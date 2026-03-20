"""Test Green Planet Energy setup."""

from unittest.mock import AsyncMock

from greenplanet_energy_api import (
    GreenPlanetEnergyAPIError,
    GreenPlanetEnergyConnectionError,
)
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.common import MockConfigEntry


async def test_setup_entry(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test setting up config entry."""
    assert init_integration.state is ConfigEntryState.LOADED


async def test_unload_entry(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test unloading config entry."""
    assert init_integration.state is ConfigEntryState.LOADED

    result = await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()

    assert result
    assert init_integration.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    "side_effect",
    [
        GreenPlanetEnergyConnectionError("timeout"),
        GreenPlanetEnergyAPIError("bad response"),
    ],
)
async def test_coordinator_update_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api,
    side_effect: Exception,
) -> None:
    """Test that API errors are wrapped in UpdateFailed during data refresh."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Override the mock to raise an error on the next refresh attempt.
    mock_api.get_electricity_prices = AsyncMock(side_effect=side_effect)

    coordinator = mock_config_entry.runtime_data
    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()
