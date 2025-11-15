"""Test the Green Planet Energy coordinator."""

from homeassistant.components.green_planet_energy.coordinator import (
    GreenPlanetEnergyUpdateCoordinator,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_coordinator_update_success(
    hass: HomeAssistant, mock_api, mock_config_entry: MockConfigEntry
) -> None:
    """Test successful data update."""
    mock_config_entry.add_to_hass(hass)
    coordinator = GreenPlanetEnergyUpdateCoordinator(hass, mock_config_entry)

    # Perform update using async_refresh
    await coordinator.async_refresh()

    assert coordinator.data is not None
    assert isinstance(coordinator.data, dict)
