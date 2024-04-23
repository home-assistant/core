"""Test sensor of AccuWeather integration."""

from datetime import timedelta
from unittest.mock import PropertyMock, patch

from accuweather import ApiError, InvalidApiKeyError, RequestsExceededError
from aiohttp.client_exceptions import ClientConnectorError
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.accuweather.const import UPDATE_INTERVAL_DAILY_FORECAST
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_UNAVAILABLE,
    Platform,
    UnitOfLength,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util.dt import utcnow
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

from . import init_integration

from tests.common import (
    async_fire_time_changed,
    load_json_array_fixture,
    load_json_object_fixture,
    snapshot_platform,
)


async def test_sensor(
    hass: HomeAssistant,
    entity_registry_enabled_by_default: None,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test states of the sensor."""
    with patch("homeassistant.components.accuweather.PLATFORMS", [Platform.SENSOR]):
        entry = await init_integration(hass)
    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


async def test_availability(hass: HomeAssistant) -> None:
    """Ensure that we mark the entities unavailable correctly when service is offline."""
    await init_integration(hass)

    state = hass.states.get("sensor.home_cloud_ceiling")
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "3200.0"

    future = utcnow() + timedelta(minutes=60)
    with patch(
        "homeassistant.components.accuweather.AccuWeather.async_get_current_conditions",
        side_effect=ConnectionError(),
    ):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

        state = hass.states.get("sensor.home_cloud_ceiling")
        assert state
        assert state.state == STATE_UNAVAILABLE

    future = utcnow() + timedelta(minutes=120)
    with (
        patch(
            "homeassistant.components.accuweather.AccuWeather.async_get_current_conditions",
            return_value=load_json_object_fixture(
                "accuweather/current_conditions_data.json"
            ),
        ),
        patch(
            "homeassistant.components.accuweather.AccuWeather.requests_remaining",
            new_callable=PropertyMock,
            return_value=10,
        ),
    ):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

        state = hass.states.get("sensor.home_cloud_ceiling")
        assert state
        assert state.state != STATE_UNAVAILABLE
        assert state.state == "3200.0"


@pytest.mark.parametrize(
    "exception",
    [
        ApiError,
        ConnectionError,
        ClientConnectorError,
        InvalidApiKeyError,
        RequestsExceededError,
    ],
)
async def test_availability_forecast(hass: HomeAssistant, exception: Exception) -> None:
    """Ensure that we mark the entities unavailable correctly when service is offline."""
    current = load_json_object_fixture("accuweather/current_conditions_data.json")
    forecast = load_json_array_fixture("accuweather/forecast_data.json")
    entity_id = "sensor.home_hours_of_sun_day_2"

    await init_integration(hass)

    state = hass.states.get(entity_id)
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "5.7"

    with (
        patch(
            "homeassistant.components.accuweather.AccuWeather.async_get_current_conditions",
            return_value=current,
        ),
        patch(
            "homeassistant.components.accuweather.AccuWeather.async_get_daily_forecast",
            side_effect=exception,
        ),
        patch(
            "homeassistant.components.accuweather.AccuWeather.requests_remaining",
            new_callable=PropertyMock,
            return_value=10,
        ),
    ):
        async_fire_time_changed(hass, utcnow() + UPDATE_INTERVAL_DAILY_FORECAST)
        await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNAVAILABLE

    with (
        patch(
            "homeassistant.components.accuweather.AccuWeather.async_get_current_conditions",
            return_value=current,
        ),
        patch(
            "homeassistant.components.accuweather.AccuWeather.async_get_daily_forecast",
            return_value=forecast,
        ),
        patch(
            "homeassistant.components.accuweather.AccuWeather.requests_remaining",
            new_callable=PropertyMock,
            return_value=10,
        ),
    ):
        async_fire_time_changed(hass, utcnow() + UPDATE_INTERVAL_DAILY_FORECAST * 2)
        await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "5.7"


async def test_manual_update_entity(hass: HomeAssistant) -> None:
    """Test manual update entity via service homeassistant/update_entity."""
    await init_integration(hass)

    await async_setup_component(hass, "homeassistant", {})

    current = load_json_object_fixture("accuweather/current_conditions_data.json")

    with (
        patch(
            "homeassistant.components.accuweather.AccuWeather.async_get_current_conditions",
            return_value=current,
        ) as mock_current,
        patch(
            "homeassistant.components.accuweather.AccuWeather.requests_remaining",
            new_callable=PropertyMock,
            return_value=10,
        ),
    ):
        await hass.services.async_call(
            "homeassistant",
            "update_entity",
            {ATTR_ENTITY_ID: ["sensor.home_cloud_ceiling"]},
            blocking=True,
        )
    assert mock_current.call_count == 1


async def test_sensor_imperial_units(hass: HomeAssistant) -> None:
    """Test states of the sensor without forecast."""
    hass.config.units = US_CUSTOMARY_SYSTEM
    await init_integration(hass)

    state = hass.states.get("sensor.home_cloud_ceiling")
    assert state
    assert state.state == "10498.687664042"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfLength.FEET

    state = hass.states.get("sensor.home_wind_speed")
    assert state
    assert state.state == "9.0"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfSpeed.MILES_PER_HOUR

    state = hass.states.get("sensor.home_realfeel_temperature")
    assert state
    assert state.state == "77.2"
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfTemperature.FAHRENHEIT
    )


async def test_state_update(hass: HomeAssistant) -> None:
    """Ensure the sensor state changes after updating the data."""
    await init_integration(hass)

    state = hass.states.get("sensor.home_cloud_ceiling")
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "3200.0"

    future = utcnow() + timedelta(minutes=60)

    current_condition = load_json_object_fixture(
        "accuweather/current_conditions_data.json"
    )
    current_condition["Ceiling"]["Metric"]["Value"] = 3300

    with (
        patch(
            "homeassistant.components.accuweather.AccuWeather.async_get_current_conditions",
            return_value=current_condition,
        ),
        patch(
            "homeassistant.components.accuweather.AccuWeather.requests_remaining",
            new_callable=PropertyMock,
            return_value=10,
        ),
    ):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

        state = hass.states.get("sensor.home_cloud_ceiling")
        assert state
        assert state.state != STATE_UNAVAILABLE
        assert state.state == "3300"
