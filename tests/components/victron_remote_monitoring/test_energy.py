"""Test the Victron Remote Monitoring energy platform."""

from homeassistant.components.victron_remote_monitoring import energy
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_energy_solar_forecast(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test fetching the solar forecast for the energy dashboard."""
    config_entry = init_integration

    assert config_entry.state is ConfigEntryState.LOADED

    assert await energy.async_get_solar_forecast(hass, config_entry.entry_id) == {
        "wh_hours": {
            "2025-04-23T10:00:00+00:00": 5050.1,
            "2025-04-23T11:00:00+00:00": 5000.2,
            "2025-04-24T10:00:00+00:00": 2250.3,
            "2025-04-24T11:00:00+00:00": 2000.4,
            "2025-04-25T10:00:00+00:00": 1000.5,
            "2025-04-25T11:00:00+00:00": 500.6,
        }
    }


async def test_energy_missing_entry(hass: HomeAssistant) -> None:
    """Return None when config entry cannot be found."""
    assert await energy.async_get_solar_forecast(hass, "missing") is None


async def test_energy_no_solar_data(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Return None when the coordinator has no solar forecast data."""
    config_entry = init_integration
    assert config_entry.state is ConfigEntryState.LOADED

    config_entry.runtime_data.data.solar = None

    assert await energy.async_get_solar_forecast(hass, config_entry.entry_id) is None
