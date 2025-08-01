"""Test VRM Forecasts platform."""

from homeassistant.components.vrm_forecasts import energy
from homeassistant.components.vrm_forecasts.coordinator import (
    VRMForecastsDataUpdateCoordinator,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_energy_solar_forecast(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    patch_forecast_fn,
) -> None:
    """Test the energy solar forecast."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert isinstance(mock_config_entry.runtime_data, VRMForecastsDataUpdateCoordinator)

    solar_energy = await energy.async_get_solar_forecast(
        hass, mock_config_entry.entry_id
    )
    assert (
        solar_energy
        == {
            "wh_hours": {
                "2025-04-23T10:00:00+00:00": 5050.1,
                "2025-04-23T11:00:00+00:00": 5000.2,
                "2025-04-24T10:00:00+00:00": 2250.3,
                "2025-04-24T11:00:00+00:00": 2000.4,
                "2025-04-25T10:00:00+00:00": 1000.5,
                "2025-04-25T11:00:00+00:00": 500.6,
            }
        }
        or solar_energy is None
    )
