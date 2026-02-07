"""Test sensor of Google Weather integration."""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from google_weather_api import GoogleWeatherApiError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_UNAVAILABLE,
    Platform,
    UnitOfLength,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_google_weather_api: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test states of the sensor."""
    with patch("homeassistant.components.google_weather._PLATFORMS", [Platform.SENSOR]):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_availability(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_google_weather_api: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Ensure that we mark the entities unavailable correctly when service is offline."""
    entity_id = "sensor.home_temperature"
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    state = hass.states.get(entity_id)
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "13.7"

    mock_google_weather_api.async_get_current_conditions.side_effect = (
        GoogleWeatherApiError()
    )

    freezer.tick(timedelta(minutes=15))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNAVAILABLE

    mock_google_weather_api.async_get_current_conditions.side_effect = None

    freezer.tick(timedelta(minutes=15))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "13.7"
    mock_google_weather_api.async_get_current_conditions.assert_called_with(
        latitude=10.1, longitude=20.1
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_manual_update_entity(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_google_weather_api: AsyncMock,
) -> None:
    """Test manual update entity via service homeassistant/update_entity."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    await async_setup_component(hass, "homeassistant", {})

    mock_google_weather_api.async_get_current_conditions.assert_called_once_with(
        latitude=10.1, longitude=20.1
    )

    await hass.services.async_call(
        "homeassistant",
        "update_entity",
        {ATTR_ENTITY_ID: ["sensor.home_temperature"]},
        blocking=True,
    )

    assert mock_google_weather_api.async_get_current_conditions.call_count == 2


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_imperial_units(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_google_weather_api: AsyncMock,
) -> None:
    """Test states of the sensor with imperial units."""
    hass.config.units = US_CUSTOMARY_SYSTEM
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    state = hass.states.get("sensor.home_temperature")
    assert state
    assert state.state == "56.66"
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfTemperature.FAHRENHEIT
    )

    state = hass.states.get("sensor.home_wind_speed")
    assert state
    assert float(state.state) == pytest.approx(4.97097)
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfSpeed.MILES_PER_HOUR

    state = hass.states.get("sensor.home_visibility")
    assert state
    assert float(state.state) == pytest.approx(9.94194)
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfLength.MILES

    state = hass.states.get("sensor.home_atmospheric_pressure")
    assert state
    assert float(state.state) == pytest.approx(30.09578)
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfPressure.INHG


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_state_update(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_google_weather_api: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Ensure the sensor state changes after updating the data."""
    entity_id = "sensor.home_temperature"

    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "13.7"

    mock_google_weather_api.async_get_current_conditions.return_value.temperature.degrees = 15.0

    freezer.tick(timedelta(minutes=15))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "15.0"
