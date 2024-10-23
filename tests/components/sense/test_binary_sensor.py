"""The tests for Sense binary sensor platform."""

from datetime import timedelta
from unittest.mock import MagicMock

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.sense.const import ACTIVE_UPDATE_RATE
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util.dt import utcnow

from . import setup_platform
from .const import DEVICE_1_NAME, DEVICE_2_NAME

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


async def test_binary_sensors(
    hass: HomeAssistant,
    mock_sense: MagicMock,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test Sensor."""
    await setup_platform(hass, config_entry, Platform.BINARY_SENSOR)
    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


async def test_on_off_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_sense: MagicMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test the Sense binary sensors."""
    await setup_platform(hass, config_entry, BINARY_SENSOR_DOMAIN)

    state = hass.states.get(f"binary_sensor.{DEVICE_1_NAME.lower()}")
    assert state.state == STATE_UNAVAILABLE

    state = hass.states.get(f"binary_sensor.{DEVICE_2_NAME.lower()}")
    assert state.state == STATE_UNAVAILABLE

    async_fire_time_changed(hass, utcnow() + timedelta(seconds=ACTIVE_UPDATE_RATE))
    await hass.async_block_till_done()

    state = hass.states.get(f"binary_sensor.{DEVICE_1_NAME.lower()}")
    assert state.state == STATE_OFF

    state = hass.states.get(f"binary_sensor.{DEVICE_2_NAME.lower()}")
    assert state.state == STATE_OFF

    async_fire_time_changed(hass, utcnow() + timedelta(seconds=ACTIVE_UPDATE_RATE))
    await hass.async_block_till_done()

    state = hass.states.get(f"binary_sensor.{DEVICE_1_NAME.lower()}")
    assert state.state == STATE_ON

    state = hass.states.get(f"binary_sensor.{DEVICE_2_NAME.lower()}")
    assert state.state == STATE_OFF

    async_fire_time_changed(hass, utcnow() + timedelta(seconds=ACTIVE_UPDATE_RATE))
    await hass.async_block_till_done()

    state = hass.states.get(f"binary_sensor.{DEVICE_1_NAME.lower()}")
    assert state.state == STATE_ON

    state = hass.states.get(f"binary_sensor.{DEVICE_2_NAME.lower()}")
    assert state.state == STATE_ON
