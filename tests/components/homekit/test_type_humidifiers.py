"""Test different accessory types: HumidifierDehumidifier."""
from pyhap.const import (
    CATEGORY_HUMIDIFIER,
    HAP_REPR_AID,
    HAP_REPR_CHARS,
    HAP_REPR_IID,
    HAP_REPR_VALUE,
)

from homeassistant.components.homekit.const import (
    ATTR_VALUE,
    CONF_LINKED_HUMIDITY_SENSOR,
    PROP_MAX_VALUE,
    PROP_MIN_STEP,
    PROP_MIN_VALUE,
    PROP_VALID_VALUES,
)
from homeassistant.components.homekit.type_humidifiers import HumidifierDehumidifier
from homeassistant.components.humidifier import HumidifierDeviceClass
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
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    ATTR_UNIT_OF_MEASUREMENT,
    PERCENTAGE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)

from tests.common import async_mock_service


async def test_humidifier(hass, hk_driver, events):
    """Test if humidifier accessory and HA are updated accordingly."""
    entity_id = "humidifier.test"

    hass.states.async_set(entity_id, STATE_OFF)
    await hass.async_block_till_done()
    acc = HumidifierDehumidifier(
        hass, hk_driver, "HumidifierDehumidifier", entity_id, 1, None
    )
    hk_driver.add_accessory(acc)

    await acc.run()
    await hass.async_block_till_done()

    assert acc.aid == 1
    assert acc.category == CATEGORY_HUMIDIFIER

    assert acc.char_current_humidifier_dehumidifier.value == 0
    assert acc.char_target_humidifier_dehumidifier.value == 1
    assert acc.char_current_humidity.value == 0
    assert acc.char_target_humidity.value == 45.0
    assert acc.char_active.value == 0

    assert acc.char_target_humidity.properties[PROP_MAX_VALUE] == DEFAULT_MAX_HUMIDITY
    assert acc.char_target_humidity.properties[PROP_MIN_VALUE] == DEFAULT_MIN_HUMIDITY
    assert acc.char_target_humidity.properties[PROP_MIN_STEP] == 1.0
    assert acc.char_target_humidifier_dehumidifier.properties[PROP_VALID_VALUES] == {
        "Humidifier": 1
    }

    hass.states.async_set(
        entity_id,
        STATE_ON,
        {ATTR_HUMIDITY: 47},
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


async def test_dehumidifier(hass, hk_driver, events):
    """Test if dehumidifier accessory and HA are updated accordingly."""
    entity_id = "humidifier.test"

    hass.states.async_set(
        entity_id, STATE_OFF, {ATTR_DEVICE_CLASS: DEVICE_CLASS_DEHUMIDIFIER}
    )
    await hass.async_block_till_done()
    acc = HumidifierDehumidifier(
        hass, hk_driver, "HumidifierDehumidifier", entity_id, 1, None
    )
    hk_driver.add_accessory(acc)

    await acc.run()
    await hass.async_block_till_done()

    assert acc.aid == 1
    assert acc.category == CATEGORY_HUMIDIFIER

    assert acc.char_current_humidifier_dehumidifier.value == 0
    assert acc.char_target_humidifier_dehumidifier.value == 2
    assert acc.char_current_humidity.value == 0
    assert acc.char_target_humidity.value == 45.0
    assert acc.char_active.value == 0

    assert acc.char_target_humidity.properties[PROP_MAX_VALUE] == DEFAULT_MAX_HUMIDITY
    assert acc.char_target_humidity.properties[PROP_MIN_VALUE] == DEFAULT_MIN_HUMIDITY
    assert acc.char_target_humidity.properties[PROP_MIN_STEP] == 1.0
    assert acc.char_target_humidifier_dehumidifier.properties[PROP_VALID_VALUES] == {
        "Dehumidifier": 2
    }

    hass.states.async_set(
        entity_id,
        STATE_ON,
        {ATTR_HUMIDITY: 30},
    )
    await hass.async_block_till_done()
    assert acc.char_target_humidity.value == 30.0
    assert acc.char_current_humidifier_dehumidifier.value == 3
    assert acc.char_target_humidifier_dehumidifier.value == 2
    assert acc.char_active.value == 1

    hass.states.async_set(
        entity_id,
        STATE_OFF,
        {ATTR_HUMIDITY: 42},
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


async def test_hygrostat_power_state(hass, hk_driver, events):
    """Test if accessory and HA are updated accordingly."""
    entity_id = "humidifier.test"

    hass.states.async_set(
        entity_id,
        STATE_ON,
        {ATTR_HUMIDITY: 43},
    )
    await hass.async_block_till_done()
    acc = HumidifierDehumidifier(
        hass, hk_driver, "HumidifierDehumidifier", entity_id, 1, None
    )
    hk_driver.add_accessory(acc)

    await acc.run()
    await hass.async_block_till_done()

    assert acc.char_current_humidifier_dehumidifier.value == 2
    assert acc.char_target_humidifier_dehumidifier.value == 1
    assert acc.char_active.value == 1

    hass.states.async_set(
        entity_id,
        STATE_OFF,
        {ATTR_HUMIDITY: 43},
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


async def test_hygrostat_get_humidity_range(hass, hk_driver):
    """Test if humidity range is evaluated correctly."""
    entity_id = "humidifier.test"

    hass.states.async_set(
        entity_id, STATE_OFF, {ATTR_MIN_HUMIDITY: 40, ATTR_MAX_HUMIDITY: 45}
    )
    await hass.async_block_till_done()
    acc = HumidifierDehumidifier(
        hass, hk_driver, "HumidifierDehumidifier", entity_id, 1, None
    )
    hk_driver.add_accessory(acc)

    await acc.run()
    await hass.async_block_till_done()

    assert acc.char_target_humidity.properties[PROP_MAX_VALUE] == 45
    assert acc.char_target_humidity.properties[PROP_MIN_VALUE] == 40


async def test_humidifier_with_linked_humidity_sensor(hass, hk_driver):
    """Test a humidifier with a linked humidity sensor can update."""
    humidity_sensor_entity_id = "sensor.bedroom_humidity"

    hass.states.async_set(
        humidity_sensor_entity_id,
        "42.0",
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.HUMIDITY,
            ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE,
        },
    )
    await hass.async_block_till_done()
    entity_id = "humidifier.test"

    hass.states.async_set(entity_id, STATE_OFF)
    await hass.async_block_till_done()
    acc = HumidifierDehumidifier(
        hass,
        hk_driver,
        "HumidifierDehumidifier",
        entity_id,
        1,
        {CONF_LINKED_HUMIDITY_SENSOR: humidity_sensor_entity_id},
    )
    hk_driver.add_accessory(acc)

    await acc.run()
    await hass.async_block_till_done()

    assert acc.char_current_humidity.value == 42.0

    hass.states.async_set(
        humidity_sensor_entity_id,
        "43.0",
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.HUMIDITY,
            ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE,
        },
    )
    await hass.async_block_till_done()

    assert acc.char_current_humidity.value == 43.0

    hass.states.async_set(
        humidity_sensor_entity_id,
        STATE_UNAVAILABLE,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.HUMIDITY,
            ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE,
        },
    )
    await hass.async_block_till_done()

    assert acc.char_current_humidity.value == 43.0

    hass.states.async_remove(humidity_sensor_entity_id)
    await hass.async_block_till_done()

    assert acc.char_current_humidity.value == 43.0


async def test_humidifier_with_a_missing_linked_humidity_sensor(hass, hk_driver):
    """Test a humidifier with a configured linked motion sensor that is missing."""
    humidity_sensor_entity_id = "sensor.bedroom_humidity"
    entity_id = "humidifier.test"

    hass.states.async_set(entity_id, STATE_OFF)
    await hass.async_block_till_done()
    acc = HumidifierDehumidifier(
        hass,
        hk_driver,
        "HumidifierDehumidifier",
        entity_id,
        1,
        {CONF_LINKED_HUMIDITY_SENSOR: humidity_sensor_entity_id},
    )
    hk_driver.add_accessory(acc)

    await acc.run()
    await hass.async_block_till_done()

    assert acc.char_current_humidity.value == 0


async def test_humidifier_as_dehumidifier(hass, hk_driver, events, caplog):
    """Test an invalid char_target_humidifier_dehumidifier from HomeKit."""
    entity_id = "humidifier.test"

    hass.states.async_set(
        entity_id, STATE_OFF, {ATTR_DEVICE_CLASS: HumidifierDeviceClass.HUMIDIFIER}
    )
    await hass.async_block_till_done()
    acc = HumidifierDehumidifier(
        hass, hk_driver, "HumidifierDehumidifier", entity_id, 1, None
    )
    hk_driver.add_accessory(acc)

    await acc.run()
    await hass.async_block_till_done()

    assert acc.char_target_humidifier_dehumidifier.value == 1

    # Set from HomeKit
    char_target_humidifier_dehumidifier_iid = (
        acc.char_target_humidifier_dehumidifier.to_HAP()[HAP_REPR_IID]
    )

    hk_driver.set_characteristics(
        {
            HAP_REPR_CHARS: [
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_target_humidifier_dehumidifier_iid,
                    HAP_REPR_VALUE: 0,
                },
            ]
        },
        "mock_addr",
    )

    await hass.async_block_till_done()
    assert "TargetHumidifierDehumidifierState is not supported" in caplog.text
    assert len(events) == 0


async def test_dehumidifier_as_humidifier(hass, hk_driver, events, caplog):
    """Test an invalid char_target_humidifier_dehumidifier from HomeKit."""
    entity_id = "humidifier.test"

    hass.states.async_set(
        entity_id, STATE_OFF, {ATTR_DEVICE_CLASS: HumidifierDeviceClass.DEHUMIDIFIER}
    )
    await hass.async_block_till_done()
    acc = HumidifierDehumidifier(
        hass, hk_driver, "HumidifierDehumidifier", entity_id, 1, None
    )
    hk_driver.add_accessory(acc)

    await acc.run()
    await hass.async_block_till_done()

    assert acc.char_target_humidifier_dehumidifier.value == 2

    # Set from HomeKit
    char_target_humidifier_dehumidifier_iid = (
        acc.char_target_humidifier_dehumidifier.to_HAP()[HAP_REPR_IID]
    )

    hk_driver.set_characteristics(
        {
            HAP_REPR_CHARS: [
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_target_humidifier_dehumidifier_iid,
                    HAP_REPR_VALUE: 1,
                },
            ]
        },
        "mock_addr",
    )

    await hass.async_block_till_done()
    assert "TargetHumidifierDehumidifierState is not supported" in caplog.text
    assert len(events) == 0
