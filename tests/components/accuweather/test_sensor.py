"""Test sensor of AccuWeather integration."""

from unittest.mock import AsyncMock, patch

from accuweather import ApiError, InvalidApiKeyError, RequestsExceededError
from aiohttp.client_exceptions import ClientConnectorError
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.accuweather.const import (
    UPDATE_INTERVAL_DAILY_FORECAST,
    UPDATE_INTERVAL_OBSERVATION,
)
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
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

from . import init_integration

from tests.common import async_fire_time_changed, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_accuweather_client: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test states of the sensor."""
    with patch("homeassistant.components.accuweather.PLATFORMS", [Platform.SENSOR]):
        entry = await init_integration(hass)
    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


async def test_availability(
    hass: HomeAssistant,
    mock_accuweather_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Ensure that we mark the entities unavailable correctly when service is offline."""
    entity_id = "sensor.home_cloud_ceiling"
    await init_integration(hass)

    state = hass.states.get(entity_id)
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "3200.0"

    mock_accuweather_client.async_get_current_conditions.side_effect = ConnectionError

    freezer.tick(UPDATE_INTERVAL_OBSERVATION)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNAVAILABLE

    mock_accuweather_client.async_get_current_conditions.side_effect = None

    freezer.tick(UPDATE_INTERVAL_OBSERVATION)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "3200.0"


@pytest.mark.parametrize(
    "exception",
    [
        ApiError("API Error"),
        ConnectionError,
        ClientConnectorError,
        InvalidApiKeyError("Invalid API key"),
        RequestsExceededError("Requests exceeded"),
    ],
)
async def test_availability_forecast(
    hass: HomeAssistant,
    exception: Exception,
    mock_accuweather_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Ensure that we mark the entities unavailable correctly when service is offline."""
    entity_id = "sensor.home_hours_of_sun_day_2"

    await init_integration(hass)

    state = hass.states.get(entity_id)
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "5.7"

    mock_accuweather_client.async_get_daily_forecast.side_effect = exception

    freezer.tick(UPDATE_INTERVAL_DAILY_FORECAST)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNAVAILABLE

    mock_accuweather_client.async_get_daily_forecast.side_effect = None

    freezer.tick(UPDATE_INTERVAL_DAILY_FORECAST)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "5.7"


async def test_manual_update_entity(
    hass: HomeAssistant, mock_accuweather_client: AsyncMock
) -> None:
    """Test manual update entity via service homeassistant/update_entity."""
    await init_integration(hass)

    await async_setup_component(hass, "homeassistant", {})

    assert mock_accuweather_client.async_get_current_conditions.call_count == 1

    await hass.services.async_call(
        "homeassistant",
        "update_entity",
        {ATTR_ENTITY_ID: ["sensor.home_cloud_ceiling"]},
        blocking=True,
    )

    assert mock_accuweather_client.async_get_current_conditions.call_count == 2


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_imperial_units(
    hass: HomeAssistant, mock_accuweather_client: AsyncMock
) -> None:
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


async def test_state_update(
    hass: HomeAssistant,
    mock_accuweather_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Ensure the sensor state changes after updating the data."""
    entity_id = "sensor.home_cloud_ceiling"

    await init_integration(hass)

    state = hass.states.get(entity_id)
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "3200.0"

    mock_accuweather_client.async_get_current_conditions.return_value["Ceiling"][
        "Metric"
    ]["Value"] = 3300

    freezer.tick(UPDATE_INTERVAL_OBSERVATION)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "3300"
