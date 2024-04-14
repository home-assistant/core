"""Test the Advantage Air Sensor Platform."""

from datetime import timedelta
from unittest.mock import AsyncMock

from homeassistant.components.advantage_air.const import DOMAIN as ADVANTAGE_AIR_DOMAIN
from homeassistant.components.advantage_air.sensor import (
    ADVANTAGE_AIR_SERVICE_SET_TIME_TO,
    ADVANTAGE_AIR_SET_COUNTDOWN_VALUE,
)
from homeassistant.config_entries import RELOAD_AFTER_UPDATE_DELAY
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from . import add_mock_config

from tests.common import async_fire_time_changed


async def test_sensor_platform(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_get: AsyncMock,
    mock_update: AsyncMock,
) -> None:
    """Test sensor platform."""

    await add_mock_config(hass)

    # Test First TimeToOn Sensor
    entity_id = "sensor.myzone_time_to_on"
    state = hass.states.get(entity_id)
    assert state
    assert int(state.state) == 0

    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "uniqueid-ac1-timetoOn"

    value = 20

    await hass.services.async_call(
        ADVANTAGE_AIR_DOMAIN,
        ADVANTAGE_AIR_SERVICE_SET_TIME_TO,
        {ATTR_ENTITY_ID: [entity_id], ADVANTAGE_AIR_SET_COUNTDOWN_VALUE: value},
        blocking=True,
    )
    mock_update.assert_called_once()
    mock_update.reset_mock()

    # Test First TimeToOff Sensor
    entity_id = "sensor.myzone_time_to_off"
    state = hass.states.get(entity_id)
    assert state
    assert int(state.state) == 10

    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "uniqueid-ac1-timetoOff"

    value = 0
    await hass.services.async_call(
        ADVANTAGE_AIR_DOMAIN,
        ADVANTAGE_AIR_SERVICE_SET_TIME_TO,
        {ATTR_ENTITY_ID: [entity_id], ADVANTAGE_AIR_SET_COUNTDOWN_VALUE: value},
        blocking=True,
    )
    mock_update.assert_called_once()
    mock_update.reset_mock()

    # Test First Zone Vent Sensor
    entity_id = "sensor.myzone_zone_open_with_sensor_vent"
    state = hass.states.get(entity_id)
    assert state
    assert int(state.state) == 100

    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "uniqueid-ac1-z01-vent"

    # Test Second Zone Vent Sensor
    entity_id = "sensor.myzone_zone_closed_with_sensor_vent"
    state = hass.states.get(entity_id)
    assert state
    assert int(state.state) == 0

    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "uniqueid-ac1-z02-vent"

    # Test First Zone Signal Sensor
    entity_id = "sensor.myzone_zone_open_with_sensor_signal"
    state = hass.states.get(entity_id)
    assert state
    assert int(state.state) == 40

    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "uniqueid-ac1-z01-signal"

    # Test Second Zone Signal Sensor
    entity_id = "sensor.myzone_zone_closed_with_sensor_signal"
    state = hass.states.get(entity_id)
    assert state
    assert int(state.state) == 10

    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "uniqueid-ac1-z02-signal"


async def test_sensor_platform_disabled_entity(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, mock_get: AsyncMock
) -> None:
    """Test sensor platform disabled entity."""

    await add_mock_config(hass)

    # Test First Zone Temp Sensor (disabled by default)
    entity_id = "sensor.myzone_zone_open_with_sensor_temperature"

    assert not hass.states.get(entity_id)

    mock_get.reset_mock()
    entity_registry.async_update_entity(entity_id=entity_id, disabled_by=None)
    await hass.async_block_till_done(wait_background_tasks=True)

    async_fire_time_changed(
        hass,
        dt_util.utcnow() + timedelta(seconds=RELOAD_AFTER_UPDATE_DELAY + 1),
    )
    await hass.async_block_till_done(wait_background_tasks=True)
    assert len(mock_get.mock_calls) == 1

    state = hass.states.get(entity_id)
    assert state
    assert int(state.state) == 25

    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "uniqueid-ac1-z01-temp"
