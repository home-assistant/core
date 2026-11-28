"""Tests for the IRM KMI coordinator."""

import pytest
from pytest_homeassistant.common import MockConfigEntry
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import UnitOfVolumetricFlux
from homeassistant.core import HomeAssistant

from . import setup_integration
from .const import RADAR_FORECAST


@pytest.mark.usefixtures("mock_get_forecasts_coord")
@pytest.mark.parametrize(
    "forecast_fixture", ["forecast.json", "forecast_nl_with_rain_on_radar.json"]
)
async def test_radar_forecast_in_millimeters_per_hour(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test every radar rate the provider reports is converted to mm/h."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.runtime_data.weather.data.radar_forecast == snapshot


@pytest.mark.usefixtures("mock_irm_kmi_api")
async def test_radar_forecast_bounds_in_millimeters_per_hour(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the rain bounds of a radar frame are converted along with its rate."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.runtime_data.weather.data.radar_forecast[2] == {
        **RADAR_FORECAST[2],
        "native_precipitation": 2.4,
        "rain_forecast_max": 3.6,
        "rain_forecast_min": 1.2,
        "unit": UnitOfVolumetricFlux.MILLIMETERS_PER_HOUR,
    }
