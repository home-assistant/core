"""Test for the weather entity of the IRM KMI integration."""

from datetime import datetime
from unittest.mock import AsyncMock

from freezegun import freeze_time

from homeassistant.components.weather import Forecast
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@freeze_time(datetime.fromisoformat("2023-12-28T15:30:00+01:00"))
async def test_weather_nl(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_irm_kmi_api_nl: AsyncMock,
) -> None:
    """Test weather with forecast from the Netherland."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    weather = hass.data["weather"].get_entity("weather.home")
    result = await weather.async_forecast_daily()

    assert isinstance(result, list)
    assert len(result) == 7

    # When getting daily forecast, the min temperature of the current day
    # should be the min temperature of the coming night
    assert result[0]["native_templow"] == 9


@freeze_time(datetime.fromisoformat("2024-01-21T14:15:00+01:00"))
async def test_weather_higher_temp_at_night(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_irm_kmi_api_high_low_temp: AsyncMock,
) -> None:
    """Test that the templow is always lower than temperature, even when API returns the opposite."""
    # Test case for https://github.com/jdejaegh/irm-kmi-ha/issues/8
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    weather = hass.data["weather"].get_entity("weather.home")
    result: list[Forecast] = await weather.async_forecast_daily()

    for f in result:
        if f["native_temperature"] is not None and f["native_templow"] is not None:
            assert f["native_temperature"] >= f["native_templow"]

    result: list[Forecast] = await weather.async_forecast_twice_daily()

    for f in result:
        if f["native_temperature"] is not None and f["native_templow"] is not None:
            assert f["native_temperature"] >= f["native_templow"]
