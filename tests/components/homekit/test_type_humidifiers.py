"""Test different accessory types: HumidifierDehumidifier."""
from collections import namedtuple

from pyhap.const import (
    CATEGORY_HUMIDIFIER,
    HAP_REPR_AID,
    HAP_REPR_CHARS,
    HAP_REPR_IID,
    HAP_REPR_VALUE,
)
import pytest

from homeassistant.components.homekit.const import (
    ATTR_VALUE,
    CONF_LINKED_HUMIDITY_SENSOR,
    PROP_MAX_VALUE,
    PROP_MIN_STEP,
    PROP_MIN_VALUE,
)
from homeassistant.components.humidifier.const import (
    ATTR_HUMIDITY,
    ATTR_MAX_HUMIDITY,
    ATTR_MIN_HUMIDITY,
    DEFAULT_MAX_HUMIDITY,
    DEFAULT_MIN_HUMIDITY,
    DEVICE_CLASS_DEHUMIDIFIER,
    DEVICE_CLASS_HUMIDIFIER,
    DOMAIN,
    SERVICE_SET_HUMIDITY,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    ATTR_UNIT_OF_MEASUREMENT,
    DEVICE_CLASS_HUMIDITY,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)

from tests.common import async_mock_service
from tests.components.homekit.common import patch_debounce


@pytest.fixture(scope="module")
def cls():
    """Patch debounce decorator during import of type_humidifiers."""
    patcher = patch_debounce()
    patcher.start()
    _import = __import__(
        "homeassistant.components.homekit.type_humidifiers",
        fromlist=["HumidifierDehumidifier"],
    )
    patcher_tuple = namedtuple("Cls", ["hygrostat"])
    yield patcher_tuple(hygrostat=_import.HumidifierDehumidifier)
    patcher.stop()


async def test_humidifier(hass, hk_driver, cls, events):
    """Test if humidifier accessory and HA are updated accordingly."""
    entity_id = "humidifier.test"

    hass.states.async_set(entity_id, STATE_OFF)
    await hass.async_block_till_done()
    acc = cls.hygrostat(hass, hk_driver, "HumidifierDehumidifier", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    await acc.run_handler()
    await hass.async_block_till_done()

    assert acc.aid == 1
    assert acc.category == CATEGORY_HUMIDIFIER

    assert acc.char_current_humidifier_dehumidifier.value == 0
    assert acc.char_target_humidifier_dehumidifier.value == 0
    assert acc.char_current_humidity.value == 0
    assert acc.char_target_humidity.value == 45.0
    assert acc.char_active.value == 0

    assert acc.char_target_humidity.properties[PROP_MAX_VALUE] == DEFAULT_MAX_HUMIDITY
    assert acc.char_target_humidity.properties[PROP_MIN_VALUE] == DEFAULT_MIN_HUMIDITY
    assert acc.char_target_humidity.properties[PROP_MIN_STEP] == 1.0

    hass.states.async_set(
        entity_id, STATE_ON, {ATTR_HUMIDITY: 47},
    )
    await hass.async_block_till_done()
    assert acc.char_target_humidity.value == 47.0
    assert acc.char_current_humidifier_dehumidifier.value == 2
    assert acc.char_target_humidifier_dehumidifier.value == 1
    assert acc.char_active.value == 1

    hass.states.async_set(
        entity_id,
        STATE_OFF,
        {ATTR_HUMIDITY: 42, ATTR_DEVICE_CLASS: DEVICE_CLASS_HUMIDIFIER},
    )
    await hass.async_block_till_done()
    assert acc.char_target_humidity.value == 42.0
    assert acc.char_current_humidifier_dehumidifier.value == 0
    assert acc.char_target_humidifier_dehumidifier.value == 1
    assert acc.char_active.value == 0

    # Set from HomeKit
    call_set_humidity = async_mock_service(hass, DOMAIN, SERVICE_SET_HUMIDITY)

    char_target_humidity_iid = acc.char_target_humidity.to_HAP()[HAP_REPR_IID]

    hk_driver.set_characteristics(
        {
            HAP_REPR_CHARS: [
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_target_humidity_iid,
                    HAP_REPR_VALUE: 39.0,
                },
            ]
        },
        "mock_addr",
    )

    await hass.async_block_till_done()
    assert len(call_set_humidity) == 1
    assert call_set_humidity[0].data[ATTR_ENTITY_ID] == entity_id
    assert call_set_humidity[0].data[ATTR_HUMIDITY] == 39.0
    assert acc.char_target_humidity.value == 39.0
    assert len(events) == 1
    assert events[-1].data[ATTR_VALUE] == "RelativeHumidityHumidifierThreshold to 39.0%"


async def test_dehumidifier(hass, hk_driver, cls, events):
    """Test if dehumidifier accessory and HA are updated accordingly."""
    entity_id = "humidifier.test"

    hass.states.async_set(
        entity_id, STATE_OFF, {ATTR_DEVICE_CLASS: DEVICE_CLASS_DEHUMIDIFIER}
    )
    await hass.async_block_till_done()
    acc = cls.hygrostat(hass, hk_driver, "HumidifierDehumidifier", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    await acc.run_handler()
    await hass.async_block_till_done()

    assert acc.aid == 1
    assert acc.category == CATEGORY_HUMIDIFIER

    assert acc.char_current_humidifier_dehumidifier.value == 0
    assert acc.char_target_humidifier_dehumidifier.value == 0
    assert acc.char_current_humidity.value == 0
    assert acc.char_target_humidity.value == 45.0
    assert acc.char_active.value == 0

    assert acc.char_target_humidity.properties[PROP_MAX_VALUE] == DEFAULT_MAX_HUMIDITY
    assert acc.char_target_humidity.properties[PROP_MIN_VALUE] == DEFAULT_MIN_HUMIDITY
    assert acc.char_target_humidity.properties[PROP_MIN_STEP] == 1.0

    hass.states.async_set(
        entity_id, STATE_ON, {ATTR_HUMIDITY: 30},
    )
    await hass.async_block_till_done()
    assert acc.char_target_humidity.value == 30.0
    assert acc.char_current_humidifier_dehumidifier.value == 3
    assert acc.char_target_humidifier_dehumidifier.value == 2
    assert acc.char_active.value == 1

    hass.states.async_set(
        entity_id, STATE_OFF, {ATTR_HUMIDITY: 42},
    )
    await hass.async_block_till_done()
    assert acc.char_target_humidity.value == 42.0
    assert acc.char_current_humidifier_dehumidifier.value == 0
    assert acc.char_target_humidifier_dehumidifier.value == 2
    assert acc.char_active.value == 0

    # Set from HomeKit
    call_set_humidity = async_mock_service(hass, DOMAIN, SERVICE_SET_HUMIDITY)

    char_target_humidity_iid = acc.char_target_humidity.to_HAP()[HAP_REPR_IID]

    hk_driver.set_characteristics(
        {
            HAP_REPR_CHARS: [
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_target_humidity_iid,
                    HAP_REPR_VALUE: 39.0,
                },
            ]
        },
        "mock_addr",
    )

    await hass.async_block_till_done()
    assert len(call_set_humidity) == 1
    assert call_set_humidity[0].data[ATTR_ENTITY_ID] == entity_id
    assert call_set_humidity[0].data[ATTR_HUMIDITY] == 39.0
    assert acc.char_target_humidity.value == 39.0
    assert len(events) == 1
    assert (
        events[-1].data[ATTR_VALUE] == "RelativeHumidityDehumidifierThreshold to 39.0%"
    )


async def test_hygrostat_power_state(hass, hk_driver, cls, events):
    """Test if accessory and HA are updated accordingly."""
    entity_id = "humidifier.test"

    hass.states.async_set(
        entity_id, STATE_ON, {ATTR_HUMIDITY: 43},
    )
    await hass.async_block_till_done()
    acc = cls.hygrostat(hass, hk_driver, "HumidifierDehumidifier", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    await acc.run_handler()
    await hass.async_block_till_done()

    assert acc.char_current_humidifier_dehumidifier.value == 2
    assert acc.char_target_humidifier_dehumidifier.value == 1
    assert acc.char_active.value == 1

    hass.states.async_set(
        entity_id, STATE_OFF, {ATTR_HUMIDITY: 43},
    )
    await hass.async_block_till_done()
    assert acc.char_current_humidifier_dehumidifier.value == 0
    assert acc.char_target_humidifier_dehumidifier.value == 1
    assert acc.char_active.value == 0

    # Set from HomeKit
    call_turn_on = async_mock_service(hass, DOMAIN, SERVICE_TURN_ON)

    char_active_iid = acc.char_active.to_HAP()[HAP_REPR_IID]

    hk_driver.set_characteristics(
        {
            HAP_REPR_CHARS: [
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_active_iid,
                    HAP_REPR_VALUE: 1,
                },
            ]
        },
        "mock_addr",
    )

    await hass.async_block_till_done()
    assert len(call_turn_on) == 1
    assert call_turn_on[0].data[ATTR_ENTITY_ID] == entity_id
    assert acc.char_active.value == 1
    assert len(events) == 1
    assert events[-1].data[ATTR_VALUE] == "Active to 1"

    call_turn_off = async_mock_service(hass, DOMAIN, SERVICE_TURN_OFF)

    hk_driver.set_characteristics(
        {
            HAP_REPR_CHARS: [
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_active_iid,
                    HAP_REPR_VALUE: 0,
                },
            ]
        },
        "mock_addr",
    )

    await hass.async_block_till_done()
    assert len(call_turn_off) == 1
    assert call_turn_off[0].data[ATTR_ENTITY_ID] == entity_id
    assert acc.char_active.value == 0
    assert len(events) == 2
    assert events[-1].data[ATTR_VALUE] == "Active to 0"


async def test_hygrostat_get_humidity_range(hass, hk_driver, cls):
    """Test if humidity range is evaluated correctly."""
    entity_id = "humidifier.test"

    hass.states.async_set(
        entity_id, STATE_OFF, {ATTR_MIN_HUMIDITY: 40, ATTR_MAX_HUMIDITY: 45}
    )
    await hass.async_block_till_done()
    acc = cls.hygrostat(hass, hk_driver, "HumidifierDehumidifier", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    await acc.run_handler()
    await hass.async_block_till_done()

    assert acc.char_target_humidity.properties[PROP_MAX_VALUE] == 45
    assert acc.char_target_humidity.properties[PROP_MIN_VALUE] == 40


async def test_humidifier_with_linked_humidity_sensor(hass, hk_driver, cls):
    """Test a humidifier with a linked humidity sensor can update."""
    humidity_sensor_entity_id = "sensor.bedroom_humidity"

    hass.states.async_set(
        humidity_sensor_entity_id,
        "42.0",
        {ATTR_DEVICE_CLASS: DEVICE_CLASS_HUMIDITY, ATTR_UNIT_OF_MEASUREMENT: "%"},
    )
    await hass.async_block_till_done()
    entity_id = "humidifier.test"

    hass.states.async_set(entity_id, STATE_OFF)
    await hass.async_block_till_done()
    acc = cls.hygrostat(
        hass,
        hk_driver,
        "HumidifierDehumidifier",
        entity_id,
        1,
        {CONF_LINKED_HUMIDITY_SENSOR: humidity_sensor_entity_id},
    )
    hk_driver.add_accessory(acc)

    await acc.run_handler()
    await hass.async_block_till_done()

    assert acc.char_current_humidity.value == 42.0

    hass.states.async_set(
        humidity_sensor_entity_id, "43.0", {ATTR_DEVICE_CLASS: DEVICE_CLASS_HUMIDITY}
    )
    await hass.async_block_till_done()

    assert acc.char_current_humidity.value == 43.0


async def test_humidifier_with_a_missing_linked_humidity_sensor(hass, hk_driver, cls):
    """Test a humidifier with a configured linked motion sensor that is missing."""
    humidity_sensor_entity_id = "sensor.bedroom_humidity"
    entity_id = "humidifier.test"

    hass.states.async_set(entity_id, STATE_OFF)
    await hass.async_block_till_done()
    acc = cls.hygrostat(
        hass,
        hk_driver,
        "HumidifierDehumidifier",
        entity_id,
        1,
        {CONF_LINKED_HUMIDITY_SENSOR: humidity_sensor_entity_id},
    )
    hk_driver.add_accessory(acc)

    await acc.run_handler()
    await hass.async_block_till_done()

    assert acc.char_current_humidity.value == 0
