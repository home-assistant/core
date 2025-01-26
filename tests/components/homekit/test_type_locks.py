"""Test different accessory types: Locks."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components import lock
from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.event import EventDeviceClass
from homeassistant.components.homekit.accessories import HomeBridge
from homeassistant.components.homekit.const import (
    ATTR_VALUE,
    CHAR_PROGRAMMABLE_SWITCH_EVENT,
    CONF_LINKED_DOORBELL_SENSOR,
    SERV_DOORBELL,
    SERV_STATELESS_PROGRAMMABLE_SWITCH,
)
from homeassistant.components.homekit.type_locks import Lock
from homeassistant.components.lock import DOMAIN as LOCK_DOMAIN, LockState
from homeassistant.const import (
    ATTR_CODE,
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import Event, HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import async_mock_service


async def test_lock_unlock(hass: HomeAssistant, hk_driver, events: list[Event]) -> None:
    """Test if accessory and HA are updated accordingly."""
    code = "1234"
    config = {ATTR_CODE: code}
    entity_id = "lock.kitchen_door"

    hass.states.async_set(entity_id, None)
    await hass.async_block_till_done()
    acc = Lock(hass, hk_driver, "Lock", entity_id, 2, config)
    acc.run()

    assert acc.aid == 2
    assert acc.category == 6  # DoorLock

    assert acc.char_current_state.value == 3
    assert acc.char_target_state.value == 1

    hass.states.async_set(entity_id, LockState.LOCKED)
    await hass.async_block_till_done()
    assert acc.char_current_state.value == 1
    assert acc.char_target_state.value == 1

    hass.states.async_set(entity_id, LockState.LOCKING)
    await hass.async_block_till_done()
    assert acc.char_current_state.value == 0
    assert acc.char_target_state.value == 1

    hass.states.async_set(entity_id, LockState.UNLOCKED)
    await hass.async_block_till_done()
    assert acc.char_current_state.value == 0
    assert acc.char_target_state.value == 0

    hass.states.async_set(entity_id, LockState.UNLOCKING)
    await hass.async_block_till_done()
    assert acc.char_current_state.value == 1
    assert acc.char_target_state.value == 0

    hass.states.async_set(entity_id, LockState.JAMMED)
    await hass.async_block_till_done()
    assert acc.char_current_state.value == 2
    assert acc.char_target_state.value == 0

    hass.states.async_set(entity_id, STATE_UNKNOWN)
    await hass.async_block_till_done()
    assert acc.char_current_state.value == 2
    assert acc.char_target_state.value == 0

    # Unavailable should keep last state
    # but set the accessory to not available
    hass.states.async_set(entity_id, STATE_UNAVAILABLE)
    await hass.async_block_till_done()
    assert acc.char_current_state.value == 2
    assert acc.char_target_state.value == 0
    assert acc.available is False

    hass.states.async_set(entity_id, LockState.UNLOCKED)
    await hass.async_block_till_done()
    assert acc.char_current_state.value == 0
    assert acc.char_target_state.value == 0
    assert acc.available is True

    # Unavailable should keep last state
    # but set the accessory to not available
    hass.states.async_set(entity_id, STATE_UNAVAILABLE)
    await hass.async_block_till_done()
    assert acc.char_current_state.value == 0
    assert acc.char_target_state.value == 0
    assert acc.available is False

    hass.states.async_remove(entity_id)
    await hass.async_block_till_done()
    assert acc.char_current_state.value == 0
    assert acc.char_target_state.value == 0

    # Set from HomeKit
    call_lock = async_mock_service(hass, LOCK_DOMAIN, "lock")
    call_unlock = async_mock_service(hass, LOCK_DOMAIN, "unlock")

    acc.char_target_state.client_update_value(1)
    await hass.async_block_till_done()
    assert call_lock
    assert call_lock[0].data[ATTR_ENTITY_ID] == entity_id
    assert call_lock[0].data[ATTR_CODE] == code
    assert acc.char_target_state.value == 1
    assert len(events) == 1
    assert events[-1].data[ATTR_VALUE] is None

    acc.char_target_state.client_update_value(0)
    await hass.async_block_till_done()
    assert call_unlock
    assert call_unlock[0].data[ATTR_ENTITY_ID] == entity_id
    assert call_unlock[0].data[ATTR_CODE] == code
    assert acc.char_target_state.value == 0
    assert len(events) == 2
    assert events[-1].data[ATTR_VALUE] is None


@pytest.mark.parametrize("config", [{}, {ATTR_CODE: None}])
async def test_no_code(
    hass: HomeAssistant, hk_driver, config, events: list[Event]
) -> None:
    """Test accessory if lock doesn't require a code."""
    entity_id = "lock.kitchen_door"

    hass.states.async_set(entity_id, None)
    await hass.async_block_till_done()
    acc = Lock(hass, hk_driver, "Lock", entity_id, 2, config)

    # Set from HomeKit
    call_lock = async_mock_service(hass, LOCK_DOMAIN, "lock")

    acc.char_target_state.client_update_value(1)
    await hass.async_block_till_done()
    assert call_lock
    assert call_lock[0].data[ATTR_ENTITY_ID] == entity_id
    assert ATTR_CODE not in call_lock[0].data
    assert acc.char_target_state.value == 1
    assert len(events) == 1
    assert events[-1].data[ATTR_VALUE] is None


async def test_lock_with_linked_doorbell_sensor(hass: HomeAssistant, hk_driver) -> None:
    """Test a lock with a linked doorbell sensor can update."""
    code = "1234"
    await async_setup_component(hass, lock.DOMAIN, {lock.DOMAIN: {"platform": "demo"}})
    await hass.async_block_till_done()
    doorbell_entity_id = "binary_sensor.doorbell"

    hass.states.async_set(
        doorbell_entity_id,
        STATE_ON,
        {ATTR_DEVICE_CLASS: BinarySensorDeviceClass.OCCUPANCY},
    )
    await hass.async_block_till_done()
    entity_id = "lock.demo_lock"

    hass.states.async_set(entity_id, None)
    await hass.async_block_till_done()
    acc = Lock(
        hass,
        hk_driver,
        "Lock",
        entity_id,
        2,
        {
            ATTR_CODE: code,
            CONF_LINKED_DOORBELL_SENSOR: doorbell_entity_id,
        },
    )
    bridge = HomeBridge("hass", hk_driver, "Test Bridge")
    bridge.add_accessory(acc)

    acc.run()

    assert acc.aid == 2
    assert acc.category == 6  # DoorLock

    service = acc.get_service(SERV_DOORBELL)
    assert service
    char = service.get_characteristic(CHAR_PROGRAMMABLE_SWITCH_EVENT)
    assert char

    assert char.value is None

    service2 = acc.get_service(SERV_STATELESS_PROGRAMMABLE_SWITCH)
    assert service2
    char2 = service.get_characteristic(CHAR_PROGRAMMABLE_SWITCH_EVENT)
    assert char2
    broker = MagicMock()
    char2.broker = broker
    assert char2.value is None

    hass.states.async_set(
        doorbell_entity_id,
        STATE_OFF,
        {ATTR_DEVICE_CLASS: BinarySensorDeviceClass.OCCUPANCY},
    )
    await hass.async_block_till_done()
    assert char.value is None
    assert char2.value is None
    assert len(broker.mock_calls) == 0

    char.set_value(True)
    char2.set_value(True)
    broker.reset_mock()

    hass.states.async_set(
        doorbell_entity_id,
        STATE_ON,
        {ATTR_DEVICE_CLASS: BinarySensorDeviceClass.OCCUPANCY},
    )
    await hass.async_block_till_done()
    assert char.value is None
    assert char2.value is None
    assert len(broker.mock_calls) == 2
    broker.reset_mock()

    hass.states.async_set(
        doorbell_entity_id,
        STATE_ON,
        {ATTR_DEVICE_CLASS: BinarySensorDeviceClass.OCCUPANCY},
        force_update=True,
    )
    await hass.async_block_till_done()
    assert char.value is None
    assert char2.value is None
    assert len(broker.mock_calls) == 0
    broker.reset_mock()

    hass.states.async_set(
        doorbell_entity_id,
        STATE_ON,
        {ATTR_DEVICE_CLASS: BinarySensorDeviceClass.OCCUPANCY, "other": "attr"},
    )
    await hass.async_block_till_done()
    assert char.value is None
    assert char2.value is None
    assert len(broker.mock_calls) == 0
    broker.reset_mock()

    # Ensure we do not throw when the linked
    # doorbell sensor is removed
    hass.states.async_remove(doorbell_entity_id)
    await hass.async_block_till_done()
    acc.run()
    await hass.async_block_till_done()
    assert char.value is None
    assert char2.value is None


async def test_lock_with_linked_doorbell_event(hass: HomeAssistant, hk_driver) -> None:
    """Test a lock with a linked doorbell event can update."""
    await async_setup_component(hass, lock.DOMAIN, {lock.DOMAIN: {"platform": "demo"}})
    await hass.async_block_till_done()
    doorbell_entity_id = "event.doorbell"
    code = "1234"

    hass.states.async_set(
        doorbell_entity_id,
        dt_util.utcnow().isoformat(),
        {ATTR_DEVICE_CLASS: EventDeviceClass.DOORBELL},
    )
    await hass.async_block_till_done()
    entity_id = "lock.demo_lock"

    hass.states.async_set(entity_id, None)
    await hass.async_block_till_done()
    acc = Lock(
        hass,
        hk_driver,
        "Lock",
        entity_id,
        2,
        {
            ATTR_CODE: code,
            CONF_LINKED_DOORBELL_SENSOR: doorbell_entity_id,
        },
    )
    bridge = HomeBridge("hass", hk_driver, "Test Bridge")
    bridge.add_accessory(acc)

    acc.run()

    assert acc.aid == 2
    assert acc.category == 6  # DoorLock

    service = acc.get_service(SERV_DOORBELL)
    assert service
    char = service.get_characteristic(CHAR_PROGRAMMABLE_SWITCH_EVENT)
    assert char

    assert char.value is None

    service2 = acc.get_service(SERV_STATELESS_PROGRAMMABLE_SWITCH)
    assert service2
    char2 = service.get_characteristic(CHAR_PROGRAMMABLE_SWITCH_EVENT)
    assert char2
    broker = MagicMock()
    char2.broker = broker
    assert char2.value is None

    hass.states.async_set(
        doorbell_entity_id,
        STATE_UNKNOWN,
        {ATTR_DEVICE_CLASS: EventDeviceClass.DOORBELL},
    )
    await hass.async_block_till_done()
    assert char.value is None
    assert char2.value is None
    assert len(broker.mock_calls) == 0

    char.set_value(True)
    char2.set_value(True)
    broker.reset_mock()

    original_time = dt_util.utcnow().isoformat()
    hass.states.async_set(
        doorbell_entity_id,
        original_time,
        {ATTR_DEVICE_CLASS: EventDeviceClass.DOORBELL},
    )
    await hass.async_block_till_done()
    assert char.value is None
    assert char2.value is None
    assert len(broker.mock_calls) == 2
    broker.reset_mock()

    hass.states.async_set(
        doorbell_entity_id,
        original_time,
        {ATTR_DEVICE_CLASS: EventDeviceClass.DOORBELL},
        force_update=True,
    )
    await hass.async_block_till_done()
    assert char.value is None
    assert char2.value is None
    assert len(broker.mock_calls) == 0
    broker.reset_mock()

    hass.states.async_set(
        doorbell_entity_id,
        original_time,
        {ATTR_DEVICE_CLASS: EventDeviceClass.DOORBELL, "other": "attr"},
    )
    await hass.async_block_till_done()
    assert char.value is None
    assert char2.value is None
    assert len(broker.mock_calls) == 0
    broker.reset_mock()

    # Ensure we do not throw when the linked
    # doorbell sensor is removed
    hass.states.async_remove(doorbell_entity_id)
    await hass.async_block_till_done()
    acc.run()
    await hass.async_block_till_done()
    assert char.value is None
    assert char2.value is None

    await hass.async_block_till_done()
    hass.states.async_set(
        doorbell_entity_id,
        STATE_UNAVAILABLE,
        {ATTR_DEVICE_CLASS: EventDeviceClass.DOORBELL},
    )
    await hass.async_block_till_done()
    # Ensure re-adding does not fire an event
    assert not broker.mock_calls
    broker.reset_mock()

    # going from unavailable to a state should not fire an event
    hass.states.async_set(
        doorbell_entity_id,
        dt_util.utcnow().isoformat(),
        {ATTR_DEVICE_CLASS: EventDeviceClass.DOORBELL},
    )
    await hass.async_block_till_done()
    assert not broker.mock_calls

    # But a second update does
    hass.states.async_set(
        doorbell_entity_id,
        dt_util.utcnow().isoformat(),
        {ATTR_DEVICE_CLASS: EventDeviceClass.DOORBELL},
    )
    await hass.async_block_till_done()
    assert broker.mock_calls


async def test_lock_with_a_missing_linked_doorbell_sensor(
    hass: HomeAssistant, hk_driver
) -> None:
    """Test a lock with a configured linked doorbell sensor that is missing."""
    await async_setup_component(hass, lock.DOMAIN, {lock.DOMAIN: {"platform": "demo"}})
    await hass.async_block_till_done()
    code = "1234"
    doorbell_entity_id = "binary_sensor.doorbell"
    entity_id = "lock.demo_lock"
    hass.states.async_set(entity_id, None)
    await hass.async_block_till_done()
    acc = Lock(
        hass,
        hk_driver,
        "Lock",
        entity_id,
        2,
        {
            ATTR_CODE: code,
            CONF_LINKED_DOORBELL_SENSOR: doorbell_entity_id,
        },
    )
    bridge = HomeBridge("hass", hk_driver, "Test Bridge")
    bridge.add_accessory(acc)

    acc.run()

    assert acc.aid == 2
    assert acc.category == 6  # DoorLock

    assert not acc.get_service(SERV_DOORBELL)
    assert not acc.get_service(SERV_STATELESS_PROGRAMMABLE_SWITCH)
