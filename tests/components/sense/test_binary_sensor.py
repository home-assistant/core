"""The tests for Sense binary sensor platform."""

from datetime import timedelta
from unittest.mock import MagicMock

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass,
)
from homeassistant.components.sense.const import ACTIVE_UPDATE_RATE
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_FRIENDLY_NAME,
    ATTR_ICON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util.dt import utcnow

from .conftest import (
    DEVICE_1_ICON,
    DEVICE_1_ID,
    DEVICE_1_NAME,
    DEVICE_2_ICON,
    DEVICE_2_ID,
    DEVICE_2_NAME,
    MONITOR_ID,
    setup_platform,
)

from tests.common import async_fire_time_changed


async def test_on_off_sensors(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, mock_sense: MagicMock
) -> None:
    """Test the Sense binary sensors."""
    await setup_platform(hass, BINARY_SENSOR_DOMAIN)

    entity = entity_registry.async_get(f"binary_sensor.{DEVICE_1_NAME.lower()}")
    assert entity
    assert entity.unique_id == f"{MONITOR_ID}-{DEVICE_1_ID}"

    entity = entity_registry.async_get(f"binary_sensor.{DEVICE_2_NAME.lower()}")
    assert entity
    assert entity.unique_id == f"{MONITOR_ID}-{DEVICE_2_ID}"

    state = hass.states.get(f"binary_sensor.{DEVICE_1_NAME.lower()}")
    assert state.state == STATE_UNAVAILABLE
    assert state.attributes.get(ATTR_ICON) == f"mdi:{DEVICE_1_ICON}"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == BinarySensorDeviceClass.POWER
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == DEVICE_1_NAME

    state = hass.states.get(f"binary_sensor.{DEVICE_2_NAME.lower()}")
    assert state.state == STATE_UNAVAILABLE
    assert state.attributes.get(ATTR_ICON) == f"mdi:{DEVICE_2_ICON}"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == BinarySensorDeviceClass.POWER
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == DEVICE_2_NAME

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
