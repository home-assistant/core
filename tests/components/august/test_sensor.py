"""The sensor tests for the august platform."""

from typing import Any

from homeassistant import core as ha
from homeassistant.const import (
    ATTR_ENTITY_PICTURE,
    ATTR_UNIT_OF_MEASUREMENT,
    PERCENTAGE,
    STATE_UNKNOWN,
)
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.helpers import entity_registry as er

from .mocks import (
    _create_august_with_devices,
    _mock_activities_from_fixture,
    _mock_doorbell_from_fixture,
    _mock_doorsense_enabled_august_lock_detail,
    _mock_lock_from_fixture,
)

from tests.common import mock_restore_cache_with_extra_data


async def test_create_doorbell(hass: HomeAssistant) -> None:
    """Test creation of a doorbell."""
    doorbell_one = await _mock_doorbell_from_fixture(hass, "get_doorbell.json")
    await _create_august_with_devices(hass, [doorbell_one])

    battery_state = hass.states.get("sensor.k98gidt45gul_name_battery")
    assert battery_state.state == "96"
    assert battery_state.attributes["unit_of_measurement"] == PERCENTAGE


async def test_create_doorbell_offline(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test creation of a doorbell that is offline."""
    doorbell_one = await _mock_doorbell_from_fixture(hass, "get_doorbell.offline.json")
    await _create_august_with_devices(hass, [doorbell_one])

    battery_state = hass.states.get("sensor.tmt100_name_battery")
    assert battery_state.state == "81"
    assert battery_state.attributes["unit_of_measurement"] == PERCENTAGE

    entry = entity_registry.async_get("sensor.tmt100_name_battery")
    assert entry
    assert entry.unique_id == "tmt100_device_battery"


async def test_create_doorbell_hardwired(hass: HomeAssistant) -> None:
    """Test creation of a doorbell that is hardwired without a battery."""
    doorbell_one = await _mock_doorbell_from_fixture(
        hass, "get_doorbell.nobattery.json"
    )
    await _create_august_with_devices(hass, [doorbell_one])

    assert hass.states.get("sensor.tmt100_name_battery") is None


async def test_create_lock_with_linked_keypad(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test creation of a lock with a linked keypad that both have a battery."""
    lock_one = await _mock_lock_from_fixture(hass, "get_lock.doorsense_init.json")
    await _create_august_with_devices(hass, [lock_one])

    battery_state = hass.states.get(
        "sensor.a6697750d607098bae8d6baa11ef8063_name_battery"
    )
    assert battery_state.state == "88"
    assert battery_state.attributes["unit_of_measurement"] == PERCENTAGE

    entry = entity_registry.async_get(
        "sensor.a6697750d607098bae8d6baa11ef8063_name_battery"
    )
    assert entry
    assert entry.unique_id == "A6697750D607098BAE8D6BAA11EF8063_device_battery"

    keypad_battery_state = hass.states.get("sensor.front_door_lock_keypad_battery")
    assert keypad_battery_state.state == "62"
    assert keypad_battery_state.attributes[ATTR_UNIT_OF_MEASUREMENT] == PERCENTAGE
    entry = entity_registry.async_get("sensor.front_door_lock_keypad_battery")
    assert entry
    assert entry.unique_id == "5bc65c24e6ef2a263e1450a8_linked_keypad_battery"


async def test_create_lock_with_low_battery_linked_keypad(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test creation of a lock with a linked keypad that both have a battery."""
    lock_one = await _mock_lock_from_fixture(hass, "get_lock.low_keypad_battery.json")
    await _create_august_with_devices(hass, [lock_one])
    states = hass.states

    battery_state = states.get("sensor.a6697750d607098bae8d6baa11ef8063_name_battery")
    assert battery_state.state == "88"
    assert battery_state.attributes["unit_of_measurement"] == PERCENTAGE
    entry = entity_registry.async_get(
        "sensor.a6697750d607098bae8d6baa11ef8063_name_battery"
    )
    assert entry
    assert entry.unique_id == "A6697750D607098BAE8D6BAA11EF8063_device_battery"

    keypad_battery_state = states.get("sensor.front_door_lock_keypad_battery")
    assert keypad_battery_state.state == "10"
    assert keypad_battery_state.attributes[ATTR_UNIT_OF_MEASUREMENT] == PERCENTAGE
    entry = entity_registry.async_get("sensor.front_door_lock_keypad_battery")
    assert entry
    assert entry.unique_id == "5bc65c24e6ef2a263e1450a8_linked_keypad_battery"

    # No activity means it will be unavailable until someone unlocks/locks it
    operator_entry = entity_registry.async_get(
        "sensor.a6697750d607098bae8d6baa11ef8063_name_operator"
    )
    assert operator_entry.unique_id == "A6697750D607098BAE8D6BAA11EF8063_lock_operator"

    operator_state = states.get("sensor.a6697750d607098bae8d6baa11ef8063_name_operator")
    assert operator_state.state == STATE_UNKNOWN


async def test_lock_operator_bluetooth(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test operation of a lock with doorsense and bridge."""
    lock_one = await _mock_doorsense_enabled_august_lock_detail(hass)

    activities = await _mock_activities_from_fixture(
        hass, "get_activity.lock_from_bluetooth.json"
    )
    await _create_august_with_devices(hass, [lock_one], activities=activities)

    lock_operator_sensor = entity_registry.async_get(
        "sensor.online_with_doorsense_name_operator"
    )
    assert lock_operator_sensor

    state = hass.states.get("sensor.online_with_doorsense_name_operator")
    assert state.state == "Your favorite elven princess"
    assert state.attributes["manual"] is False
    assert state.attributes["tag"] is False
    assert state.attributes["remote"] is False
    assert state.attributes["keypad"] is False
    assert state.attributes["autorelock"] is False
    assert state.attributes["method"] == "mobile"


async def test_lock_operator_keypad(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test operation of a lock with doorsense and bridge."""
    lock_one = await _mock_doorsense_enabled_august_lock_detail(hass)

    activities = await _mock_activities_from_fixture(
        hass, "get_activity.lock_from_keypad.json"
    )
    await _create_august_with_devices(hass, [lock_one], activities=activities)

    lock_operator_sensor = entity_registry.async_get(
        "sensor.online_with_doorsense_name_operator"
    )
    assert lock_operator_sensor

    state = hass.states.get("sensor.online_with_doorsense_name_operator")
    assert state.state == "Your favorite elven princess"
    assert state.attributes["manual"] is False
    assert state.attributes["tag"] is False
    assert state.attributes["remote"] is False
    assert state.attributes["keypad"] is True
    assert state.attributes["autorelock"] is False
    assert state.attributes["method"] == "keypad"


async def test_lock_operator_remote(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test operation of a lock with doorsense and bridge."""
    lock_one = await _mock_doorsense_enabled_august_lock_detail(hass)

    activities = await _mock_activities_from_fixture(hass, "get_activity.lock.json")
    await _create_august_with_devices(hass, [lock_one], activities=activities)

    lock_operator_sensor = entity_registry.async_get(
        "sensor.online_with_doorsense_name_operator"
    )
    assert lock_operator_sensor

    state = hass.states.get("sensor.online_with_doorsense_name_operator")
    assert state.state == "Your favorite elven princess"
    assert state.attributes["manual"] is False
    assert state.attributes["tag"] is False
    assert state.attributes["remote"] is True
    assert state.attributes["keypad"] is False
    assert state.attributes["autorelock"] is False
    assert state.attributes["method"] == "remote"


async def test_lock_operator_manual(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test operation of a lock with doorsense and bridge."""
    lock_one = await _mock_doorsense_enabled_august_lock_detail(hass)

    activities = await _mock_activities_from_fixture(
        hass, "get_activity.lock_from_manual.json"
    )
    await _create_august_with_devices(hass, [lock_one], activities=activities)

    lock_operator_sensor = entity_registry.async_get(
        "sensor.online_with_doorsense_name_operator"
    )
    assert lock_operator_sensor
    state = hass.states.get("sensor.online_with_doorsense_name_operator")
    assert state.state == "Your favorite elven princess"
    assert state.attributes["manual"] is True
    assert state.attributes["tag"] is False
    assert state.attributes["remote"] is False
    assert state.attributes["keypad"] is False
    assert state.attributes["autorelock"] is False
    assert state.attributes["method"] == "manual"


async def test_lock_operator_autorelock(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test operation of a lock with doorsense and bridge."""
    lock_one = await _mock_doorsense_enabled_august_lock_detail(hass)

    activities = await _mock_activities_from_fixture(
        hass, "get_activity.lock_from_autorelock.json"
    )
    await _create_august_with_devices(hass, [lock_one], activities=activities)

    lock_operator_sensor = entity_registry.async_get(
        "sensor.online_with_doorsense_name_operator"
    )
    assert lock_operator_sensor

    state = hass.states.get("sensor.online_with_doorsense_name_operator")
    assert state.state == "Auto Relock"
    assert state.attributes["manual"] is False
    assert state.attributes["tag"] is False
    assert state.attributes["remote"] is False
    assert state.attributes["keypad"] is False
    assert state.attributes["autorelock"] is True
    assert state.attributes["method"] == "autorelock"


async def test_unlock_operator_manual(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test operation of a lock manually."""
    lock_one = await _mock_doorsense_enabled_august_lock_detail(hass)

    activities = await _mock_activities_from_fixture(
        hass, "get_activity.unlock_from_manual.json"
    )
    await _create_august_with_devices(hass, [lock_one], activities=activities)

    lock_operator_sensor = entity_registry.async_get(
        "sensor.online_with_doorsense_name_operator"
    )
    assert lock_operator_sensor

    state = hass.states.get("sensor.online_with_doorsense_name_operator")
    assert state.state == "Your favorite elven princess"
    assert state.attributes["manual"] is True
    assert state.attributes["tag"] is False
    assert state.attributes["remote"] is False
    assert state.attributes["keypad"] is False
    assert state.attributes["autorelock"] is False
    assert state.attributes["method"] == "manual"


async def test_unlock_operator_tag(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test operation of a lock with a tag."""
    lock_one = await _mock_doorsense_enabled_august_lock_detail(hass)

    activities = await _mock_activities_from_fixture(
        hass, "get_activity.unlock_from_tag.json"
    )
    await _create_august_with_devices(hass, [lock_one], activities=activities)

    lock_operator_sensor = entity_registry.async_get(
        "sensor.online_with_doorsense_name_operator"
    )
    assert lock_operator_sensor

    state = hass.states.get("sensor.online_with_doorsense_name_operator")
    assert state.state == "Your favorite elven princess"
    assert state.attributes["manual"] is False
    assert state.attributes["tag"] is True
    assert state.attributes["remote"] is False
    assert state.attributes["keypad"] is False
    assert state.attributes["autorelock"] is False
    assert state.attributes["method"] == "tag"


async def test_restored_state(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test restored state."""

    entity_id = "sensor.online_with_doorsense_name_operator"
    lock_one = await _mock_doorsense_enabled_august_lock_detail(hass)

    fake_state = ha.State(
        entity_id,
        state="Tag Unlock",
        attributes={
            "method": "tag",
            "manual": False,
            "remote": False,
            "keypad": False,
            "tag": True,
            "autorelock": False,
            ATTR_ENTITY_PICTURE: "image.png",
        },
    )

    # Home assistant is not running yet
    hass.set_state(CoreState.not_running)
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                fake_state,
                {"native_value": "Tag Unlock", "native_unit_of_measurement": None},
            )
        ],
    )

    await _create_august_with_devices(hass, [lock_one])

    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == "Tag Unlock"
    assert state.attributes["method"] == "tag"
    assert state.attributes[ATTR_ENTITY_PICTURE] == "image.png"
