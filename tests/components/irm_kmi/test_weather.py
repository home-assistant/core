"""Test for the weather entity of the IRM KMI integration."""

from datetime import datetime
import json
from unittest.mock import MagicMock

from freezegun import freeze_time
from irm_kmi_api import IrmKmiApiClientHa

from homeassistant.components.irm_kmi.coordinator import IrmKmiCoordinator
from homeassistant.components.irm_kmi.weather import IrmKmiWeather
from homeassistant.components.weather import Forecast
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, async_load_fixture


@freeze_time(datetime.fromisoformat("2023-12-28T15:30:00+01:00"))
async def test_weather_nl(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test weather with forecast from the Netherland."""
    mock_config_entry.runtime_data = MagicMock()
    mock_config_entry.runtime_data.api_client = IrmKmiApiClientHa(MagicMock(), "test")
    forecast = json.loads(await async_load_fixture(hass, "forecast_nl.json", "irm_kmi"))
    mock_config_entry.runtime_data.api_client._api_data = forecast

    mock_config_entry.runtime_data = coordinator = IrmKmiCoordinator(
        hass, mock_config_entry, mock_config_entry.runtime_data.api_client
    )
    coordinator.data = await coordinator.process_api_data()

    weather = IrmKmiWeather(mock_config_entry)
    result = await weather.async_forecast_daily()

    assert isinstance(result, list)
    assert len(result) == 7

    # When getting daily forecast, the min temperature of the current day
    # should be the min temperature of the coming night
    assert result[0]["native_templow"] == 9


@freeze_time(datetime.fromisoformat("2024-01-21T14:15:00+01:00"))
async def test_weather_higher_temp_at_night(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that the templow is always lower than temperature, even when API returns the opposite."""
    # Test case for https://github.com/jdejaegh/irm-kmi-ha/issues/8
    mock_config_entry.runtime_data = MagicMock()
    mock_config_entry.runtime_data.api_client = IrmKmiApiClientHa(MagicMock(), "test")
    forecast = json.loads(
        await async_load_fixture(hass, "high_low_temp.json", "irm_kmi")
    )
    mock_config_entry.runtime_data.api_client._api_data = forecast

    mock_config_entry.runtime_data = coordinator = IrmKmiCoordinator(
        hass, mock_config_entry, mock_config_entry.runtime_data.api_client
    )
    coordinator.data = await coordinator.process_api_data()

    weather = IrmKmiWeather(mock_config_entry)
    result: list[Forecast] = await weather.async_forecast_daily()

    for f in result:
        if f["native_temperature"] is not None and f["native_templow"] is not None:
            assert f["native_temperature"] >= f["native_templow"]

    result: list[Forecast] = await weather.async_forecast_twice_daily()

    for f in result:
        if f["native_temperature"] is not None and f["native_templow"] is not None:
            assert f["native_temperature"] >= f["native_templow"]
