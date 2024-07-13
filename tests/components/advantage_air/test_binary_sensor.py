"""Test the Advantage Air Binary Sensor Platform."""

from datetime import timedelta
from unittest.mock import AsyncMock

from homeassistant.components.advantage_air import ADVANTAGE_AIR_SYNC_INTERVAL
from homeassistant.config_entries import RELOAD_AFTER_UPDATE_DELAY
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from . import add_mock_config

from tests.common import async_fire_time_changed


async def test_binary_sensor_async_setup_entry(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_get: AsyncMock,
) -> None:
    """Test binary sensor setup."""

    await add_mock_config(hass)

    # Test First Air Filter
    entity_id = "binary_sensor.myzone_filter"
    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OFF

    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "uniqueid-ac1-filter"

    # Test Second Air Filter
    entity_id = "binary_sensor.mytemp_filter"
    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_ON

    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "uniqueid-ac2-filter"

    # Test First Motion Sensor
    entity_id = "binary_sensor.myzone_zone_open_with_sensor_motion"
    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_ON

    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "uniqueid-ac1-z01-motion"

    # Test Second Motion Sensor
    entity_id = "binary_sensor.myzone_zone_closed_with_sensor_motion"
    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OFF

    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "uniqueid-ac1-z02-motion"

    # Test First MyZone Sensor (disabled by default)
    entity_id = "binary_sensor.myzone_zone_open_with_sensor_myzone"

    assert not hass.states.get(entity_id)

    mock_get.reset_mock()
    entity_registry.async_update_entity(entity_id=entity_id, disabled_by=None)
    await hass.async_block_till_done()

    async_fire_time_changed(
        hass,
        dt_util.utcnow() + timedelta(seconds=ADVANTAGE_AIR_SYNC_INTERVAL + 1),
    )
    await hass.async_block_till_done(wait_background_tasks=True)
    assert len(mock_get.mock_calls) == 1

    async_fire_time_changed(
        hass,
        dt_util.utcnow() + timedelta(seconds=RELOAD_AFTER_UPDATE_DELAY + 1),
    )
    await hass.async_block_till_done(wait_background_tasks=True)
    assert len(mock_get.mock_calls) == 2

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_ON

    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "uniqueid-ac1-z01-myzone"

    # Test Second Motion Sensor (disabled by default)
    entity_id = "binary_sensor.myzone_zone_closed_with_sensor_myzone"

    assert not hass.states.get(entity_id)

    mock_get.reset_mock()
    entity_registry.async_update_entity(entity_id=entity_id, disabled_by=None)
    await hass.async_block_till_done()

    async_fire_time_changed(
        hass,
        dt_util.utcnow() + timedelta(seconds=ADVANTAGE_AIR_SYNC_INTERVAL + 1),
    )
    await hass.async_block_till_done(wait_background_tasks=True)
    assert len(mock_get.mock_calls) == 1

    async_fire_time_changed(
        hass,
        dt_util.utcnow() + timedelta(seconds=RELOAD_AFTER_UPDATE_DELAY + 1),
    )
    await hass.async_block_till_done(wait_background_tasks=True)
    assert len(mock_get.mock_calls) == 2

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OFF

    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "uniqueid-ac1-z02-myzone"
