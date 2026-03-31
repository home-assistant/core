"""Tests for Forecast.Solar coordinator."""

from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock, Mock

from forecast_solar import ForecastSolarConnectionError
import pytest

from homeassistant.components.forecast_solar.const import (
    AZIMUTH_MAX,
    AZIMUTH_MIN,
    CONF_AZIMUTH,
    CONF_AZIMUTH_SENSOR,
    CONF_DECLINATION,
    CONF_DECLINATION_SENSOR,
    CONF_INVERTER_SIZE,
    CONF_MODULES_POWER,
    DECLINATION_MAX,
    DECLINATION_MIN,
)
from homeassistant.components.forecast_solar.coordinator import (
    ForecastSolarDataUpdateCoordinator,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed


def make_entry(options: dict[str, Any] | None = None) -> ConfigEntry:
    """Create a mock ConfigEntry with sensible option defaults.

    Location is always in options — the coordinator no longer checks entry.data
    for a home-location flag.
    """
    entry: ConfigEntry = Mock(spec=ConfigEntry)
    entry.options = {
        CONF_LATITUDE: 1.0,
        CONF_LONGITUDE: 2.0,
        CONF_DECLINATION: 30,
        CONF_AZIMUTH: 180,
        CONF_MODULES_POWER: 1000,
    }
    if options:
        entry.options = {**entry.options, **options}
    entry.data = {}
    return entry


async def test_location_read_from_options(hass: HomeAssistant) -> None:
    """Test that the coordinator always reads lat/lon from options."""
    entry = make_entry(options={CONF_LATITUDE: 10.0, CONF_LONGITUDE: 20.0})

    coordinator = ForecastSolarDataUpdateCoordinator(hass, entry)

    assert coordinator.forecast.latitude == 10.0
    assert coordinator.forecast.longitude == 20.0


async def test_update_interval_with_api_key(hass: HomeAssistant) -> None:
    """Test update interval when API key is provided."""
    entry = make_entry(options={CONF_API_KEY: "abc"})

    coordinator = ForecastSolarDataUpdateCoordinator(hass, entry)

    assert coordinator.update_interval == timedelta(minutes=30)


async def test_update_interval_without_api_key(hass: HomeAssistant) -> None:
    """Test update interval when API key is not provided."""
    entry = make_entry()

    coordinator = ForecastSolarDataUpdateCoordinator(hass, entry)

    assert coordinator.update_interval == timedelta(hours=1)


async def test_inverter_scaling(hass: HomeAssistant) -> None:
    """Test inverter value is scaled from watts to kilowatts."""
    entry = make_entry(options={CONF_INVERTER_SIZE: 5000})

    coordinator = ForecastSolarDataUpdateCoordinator(hass, entry)

    assert coordinator.forecast.inverter == 5.0


@pytest.mark.parametrize(
    ("sensor_type", "sensor_key", "good_val", "bad_val", "bounds_min", "bounds_max"),
    [
        (
            "declination",
            CONF_DECLINATION_SENSOR,
            25,
            999,
            DECLINATION_MIN,
            DECLINATION_MAX,
        ),
        ("azimuth", CONF_AZIMUTH_SENSOR, 200, 999, AZIMUTH_MIN, AZIMUTH_MAX),
    ],
)
async def test_sensor_values(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    sensor_type: str,
    sensor_key: str,
    good_val: float,
    bad_val: float,
    bounds_min: int,
    bounds_max: int,
) -> None:
    """Test sensor handling for both declination and azimuth with valid and invalid values."""
    # ---- valid sensor ----
    hass.states.async_set("sensor.test", str(good_val))
    entry = make_entry(options={sensor_key: "sensor.test"})
    coordinator = ForecastSolarDataUpdateCoordinator(hass, entry)

    value = (
        coordinator.forecast.declination
        if sensor_type == "declination"
        else coordinator.forecast.azimuth
    )
    expected_value = good_val if sensor_type == "declination" else good_val - 180
    assert value == expected_value

    # ---- out-of-range sensor ----
    hass.states.async_set("sensor.test", str(bad_val))
    coordinator = ForecastSolarDataUpdateCoordinator(hass, entry)
    value = (
        coordinator.forecast.declination
        if sensor_type == "declination"
        else coordinator.forecast.azimuth
    )
    assert value == 0.0
    expected_msg = (
        f"{sensor_type.capitalize()} sensor 'sensor.test' value {bad_val:.3f} "
        f"out of range [{bounds_min}, {bounds_max}]"
    )
    assert expected_msg in caplog.text
    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()

    # ---- unavailable sensor ----
    hass.states.async_set("sensor.test", "unavailable")
    coordinator = ForecastSolarDataUpdateCoordinator(hass, entry)
    value = (
        coordinator.forecast.declination
        if sensor_type == "declination"
        else coordinator.forecast.azimuth
    )
    assert value == 0.0
    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()

    # ---- non-numeric sensor ----
    hass.states.async_set("sensor.test", "abc")
    coordinator = ForecastSolarDataUpdateCoordinator(hass, entry)
    value = (
        coordinator.forecast.declination
        if sensor_type == "declination"
        else coordinator.forecast.azimuth
    )
    assert value == 0.0
    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()

    # ---- missing sensor ----
    entry = make_entry(options={sensor_key: "sensor.missing"})
    coordinator = ForecastSolarDataUpdateCoordinator(hass, entry)
    value = (
        coordinator.forecast.declination
        if sensor_type == "declination"
        else coordinator.forecast.azimuth
    )
    assert value == 0.0
    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


async def test_async_update_success(hass: HomeAssistant) -> None:
    """Test successful async data update."""
    entry = make_entry()
    coordinator = ForecastSolarDataUpdateCoordinator(hass, entry)

    coordinator.forecast.estimate = AsyncMock(return_value="ok")

    result = await coordinator._async_update_data()

    assert result == "ok"


async def test_async_update_failure(hass: HomeAssistant) -> None:
    """Test async data update failure raises UpdateFailed."""
    entry = make_entry()
    coordinator = ForecastSolarDataUpdateCoordinator(hass, entry)

    coordinator.forecast.estimate = AsyncMock(
        side_effect=ForecastSolarConnectionError("fail")
    )

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()
