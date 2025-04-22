"""Test different accessory types: Air Purifiers."""

from unittest.mock import MagicMock

from pyhap.const import HAP_REPR_AID, HAP_REPR_CHARS, HAP_REPR_IID, HAP_REPR_VALUE
import pytest

from homeassistant.components.fan import (
    ATTR_PERCENTAGE,
    ATTR_PRESET_MODE,
    ATTR_PRESET_MODES,
    DOMAIN as FAN_DOMAIN,
    FanEntityFeature,
)
from homeassistant.components.homekit import (
    CONF_LINKED_HUMIDITY_SENSOR,
    CONF_LINKED_PM25_SENSOR,
    CONF_LINKED_TEMPERATURE_SENSOR,
)
from homeassistant.components.homekit.const import (
    CONF_LINKED_FILTER_CHANGE_INDICATION,
    CONF_LINKED_FILTER_LIFE_LEVEL,
    THRESHOLD_FILTER_CHANGE_NEEDED,
)
from homeassistant.components.homekit.type_air_purifiers import (
    FILTER_CHANGE_FILTER,
    FILTER_OK,
    TARGET_STATE_AUTO,
    TARGET_STATE_MANUAL,
    AirPurifier,
)
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import Event, HomeAssistant

from tests.common import async_mock_service


@pytest.mark.parametrize(
    ("auto_preset", "preset_modes"),
    [
        ("auto", ["sleep", "smart", "auto"]),
        ("Auto", ["sleep", "smart", "Auto"]),
    ],
)
async def test_fan_auto_manual(
    hass: HomeAssistant,
    hk_driver,
    events: list[Event],
    auto_preset: str,
    preset_modes: list[str],
) -> None:
    """Test switching between Auto and Manual."""
    entity_id = "fan.demo"

    hass.states.async_set(
        entity_id,
        STATE_ON,
        {
            ATTR_SUPPORTED_FEATURES: FanEntityFeature.PRESET_MODE
            | FanEntityFeature.SET_SPEED,
            ATTR_PRESET_MODE: auto_preset,
            ATTR_PRESET_MODES: preset_modes,
        },
    )
    await hass.async_block_till_done()
    acc = AirPurifier(hass, hk_driver, "Air Purifier", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    assert acc.preset_mode_chars["smart"].value == 0
    assert acc.preset_mode_chars["sleep"].value == 0
    assert acc.auto_preset is not None

    # Auto presets are handled as the target air purifier state, so
    # not supposed to be exposed as a separate switch
    switches = set()
    for service in acc.services:
        if service.display_name == "Switch":
            switches.add(service.unique_id)

    assert len(switches) == len(preset_modes) - 1
    for preset in preset_modes:
        if preset != auto_preset:
            assert preset in switches
        else:
            # Auto preset should not be in switches
            assert preset not in switches

    acc.run()
    await hass.async_block_till_done()

    assert acc.char_target_air_purifier_state.value == TARGET_STATE_AUTO

    hass.states.async_set(
        entity_id,
        STATE_ON,
        {
            ATTR_SUPPORTED_FEATURES: FanEntityFeature.PRESET_MODE
            | FanEntityFeature.SET_SPEED,
            ATTR_PRESET_MODE: "smart",
            ATTR_PRESET_MODES: preset_modes,
        },
    )
    await hass.async_block_till_done()

    assert acc.preset_mode_chars["smart"].value == 1
    assert acc.char_target_air_purifier_state.value == TARGET_STATE_MANUAL

    # Set from HomeKit
    call_set_preset_mode = async_mock_service(hass, FAN_DOMAIN, "set_preset_mode")
    call_set_percentage = async_mock_service(hass, FAN_DOMAIN, "set_percentage")
    char_auto_iid = acc.char_target_air_purifier_state.to_HAP()[HAP_REPR_IID]

    hk_driver.set_characteristics(
        {
            HAP_REPR_CHARS: [
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_auto_iid,
                    HAP_REPR_VALUE: 1,
                },
            ]
        },
        "mock_addr",
    )
    await hass.async_block_till_done()

    assert acc.char_target_air_purifier_state.value == TARGET_STATE_AUTO
    assert len(call_set_preset_mode) == 1
    assert call_set_preset_mode[0].data[ATTR_ENTITY_ID] == entity_id
    assert call_set_preset_mode[0].data[ATTR_PRESET_MODE] == auto_preset
    assert len(events) == 1
    assert events[-1].data["service"] == "set_preset_mode"

    hk_driver.set_characteristics(
        {
            HAP_REPR_CHARS: [
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_auto_iid,
                    HAP_REPR_VALUE: 0,
                },
            ]
        },
        "mock_addr",
    )
    await hass.async_block_till_done()
    assert acc.char_target_air_purifier_state.value == TARGET_STATE_MANUAL
    assert len(call_set_percentage) == 1
    assert call_set_percentage[0].data[ATTR_ENTITY_ID] == entity_id
    assert events[-1].data["service"] == "set_percentage"
    assert len(events) == 2


async def test_presets_no_auto(
    hass: HomeAssistant,
    hk_driver,
    events: list[Event],
) -> None:
    """Test preset without an auto mode."""
    entity_id = "fan.demo"

    preset_modes = ["sleep", "smart"]
    hass.states.async_set(
        entity_id,
        STATE_ON,
        {
            ATTR_SUPPORTED_FEATURES: FanEntityFeature.PRESET_MODE
            | FanEntityFeature.SET_SPEED,
            ATTR_PRESET_MODE: "smart",
            ATTR_PRESET_MODES: preset_modes,
        },
    )
    await hass.async_block_till_done()
    acc = AirPurifier(hass, hk_driver, "Air Purifier", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    assert acc.preset_mode_chars["smart"].value == 1
    assert acc.preset_mode_chars["sleep"].value == 0
    assert acc.auto_preset is None

    # Auto presets are handled as the target air purifier state, so
    # not supposed to be exposed as a separate switch
    switches = set()
    for service in acc.services:
        if service.display_name == "Switch":
            switches.add(service.unique_id)

    assert len(switches) == len(preset_modes)
    for preset in preset_modes:
        assert preset in switches

    acc.run()
    await hass.async_block_till_done()

    assert acc.char_target_air_purifier_state.value == TARGET_STATE_MANUAL

    hass.states.async_set(
        entity_id,
        STATE_ON,
        {
            ATTR_SUPPORTED_FEATURES: FanEntityFeature.PRESET_MODE
            | FanEntityFeature.SET_SPEED,
            ATTR_PRESET_MODE: "sleep",
            ATTR_PRESET_MODES: preset_modes,
        },
    )
    await hass.async_block_till_done()

    assert acc.preset_mode_chars["smart"].value == 0
    assert acc.preset_mode_chars["sleep"].value == 1
    assert acc.char_target_air_purifier_state.value == TARGET_STATE_MANUAL


async def test_air_purifier_single_preset_mode(
    hass: HomeAssistant, hk_driver, events: list[Event]
) -> None:
    """Test air purifier with a single preset mode."""
    entity_id = "fan.demo"

    hass.states.async_set(
        entity_id,
        STATE_ON,
        {
            ATTR_SUPPORTED_FEATURES: FanEntityFeature.PRESET_MODE
            | FanEntityFeature.SET_SPEED,
            ATTR_PERCENTAGE: 42,
            ATTR_PRESET_MODE: "auto",
            ATTR_PRESET_MODES: ["auto"],
        },
    )
    await hass.async_block_till_done()
    acc = AirPurifier(hass, hk_driver, "Air Purifier", entity_id, 1, None)
    hk_driver.add_accessory(acc)

    assert acc.char_target_air_purifier_state.value == TARGET_STATE_AUTO

    acc.run()
    await hass.async_block_till_done()

    # Set from HomeKit
    call_set_preset_mode = async_mock_service(hass, FAN_DOMAIN, "set_preset_mode")
    call_set_percentage = async_mock_service(hass, FAN_DOMAIN, "set_percentage")

    char_target_air_purifier_state_iid = acc.char_target_air_purifier_state.to_HAP()[
        HAP_REPR_IID
    ]

    hk_driver.set_characteristics(
        {
            HAP_REPR_CHARS: [
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_target_air_purifier_state_iid,
                    HAP_REPR_VALUE: TARGET_STATE_MANUAL,
                },
            ]
        },
        "mock_addr",
    )
    await hass.async_block_till_done()
    assert call_set_percentage[0]
    assert call_set_percentage[0].data[ATTR_ENTITY_ID] == entity_id
    assert call_set_percentage[0].data[ATTR_PERCENTAGE] == 42
    assert len(events) == 1
    assert events[-1].data["service"] == "set_percentage"

    hk_driver.set_characteristics(
        {
            HAP_REPR_CHARS: [
                {
                    HAP_REPR_AID: acc.aid,
                    HAP_REPR_IID: char_target_air_purifier_state_iid,
                    HAP_REPR_VALUE: 1,
                },
            ]
        },
        "mock_addr",
    )
    await hass.async_block_till_done()
    assert call_set_preset_mode[0]
    assert call_set_preset_mode[0].data[ATTR_ENTITY_ID] == entity_id
    assert call_set_preset_mode[0].data[ATTR_PRESET_MODE] == "auto"
    assert events[-1].data["service"] == "set_preset_mode"
    assert len(events) == 2

    hass.states.async_set(
        entity_id,
        STATE_ON,
        {
            ATTR_SUPPORTED_FEATURES: FanEntityFeature.PRESET_MODE
            | FanEntityFeature.SET_SPEED,
            ATTR_PERCENTAGE: 42,
            ATTR_PRESET_MODE: None,
            ATTR_PRESET_MODES: ["auto"],
        },
    )
    await hass.async_block_till_done()
    assert acc.char_target_air_purifier_state.value == TARGET_STATE_MANUAL


async def test_expose_linked_sensors(
    hass: HomeAssistant, hk_driver, events: list[Event]
) -> None:
    """Test that linked sensors are exposed."""
    entity_id = "fan.demo"

    hass.states.async_set(
        entity_id,
        STATE_ON,
        {
            ATTR_SUPPORTED_FEATURES: FanEntityFeature.SET_SPEED,
        },
    )

    humidity_entity_id = "sensor.demo_humidity"
    hass.states.async_set(
        humidity_entity_id,
        50,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.HUMIDITY,
        },
    )

    pm25_entity_id = "sensor.demo_pm25"
    hass.states.async_set(
        pm25_entity_id,
        10,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.PM25,
        },
    )

    temperature_entity_id = "sensor.demo_temperature"
    hass.states.async_set(
        temperature_entity_id,
        25,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.TEMPERATURE,
        },
    )

    await hass.async_block_till_done()
    acc = AirPurifier(
        hass,
        hk_driver,
        "Air Purifier",
        entity_id,
        1,
        {
            CONF_LINKED_TEMPERATURE_SENSOR: temperature_entity_id,
            CONF_LINKED_PM25_SENSOR: pm25_entity_id,
            CONF_LINKED_HUMIDITY_SENSOR: humidity_entity_id,
        },
    )
    hk_driver.add_accessory(acc)

    assert acc.linked_humidity_sensor is not None
    assert acc.char_current_humidity is not None
    assert acc.linked_pm25_sensor is not None
    assert acc.char_pm25_density is not None
    assert acc.char_air_quality is not None
    assert acc.linked_temperature_sensor is not None
    assert acc.char_current_temperature is not None

    acc.run()
    await hass.async_block_till_done()

    assert acc.char_current_humidity.value == 50
    assert acc.char_pm25_density.value == 10
    assert acc.char_air_quality.value == 2
    assert acc.char_current_temperature.value == 25

    # Updated humidity should reflect in HomeKit
    broker = MagicMock()
    acc.char_current_humidity.broker = broker
    hass.states.async_set(
        humidity_entity_id,
        60,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.HUMIDITY,
        },
    )
    await hass.async_block_till_done()
    assert acc.char_current_humidity.value == 60
    assert len(broker.mock_calls) == 2
    broker.reset_mock()

    # Change to same state should not trigger update in HomeKit
    hass.states.async_set(
        humidity_entity_id,
        60,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.HUMIDITY,
        },
        force_update=True,
    )
    await hass.async_block_till_done()
    assert acc.char_current_humidity.value == 60
    assert len(broker.mock_calls) == 0

    # Updated PM2.5 should reflect in HomeKit
    broker = MagicMock()
    acc.char_pm25_density.broker = broker
    acc.char_air_quality.broker = broker
    hass.states.async_set(
        pm25_entity_id,
        5,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.PM25,
        },
    )
    await hass.async_block_till_done()
    assert acc.char_pm25_density.value == 5
    assert acc.char_air_quality.value == 1
    assert len(broker.mock_calls) == 4
    broker.reset_mock()

    # Change to same state should not trigger update in HomeKit
    hass.states.async_set(
        pm25_entity_id,
        5,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.PM25,
        },
        force_update=True,
    )
    await hass.async_block_till_done()
    assert acc.char_pm25_density.value == 5
    assert acc.char_air_quality.value == 1
    assert len(broker.mock_calls) == 0

    # Updated temperature should reflect in HomeKit
    broker = MagicMock()
    acc.char_current_temperature.broker = broker
    hass.states.async_set(
        temperature_entity_id,
        30,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.TEMPERATURE,
        },
    )
    await hass.async_block_till_done()
    assert acc.char_current_temperature.value == 30
    assert len(broker.mock_calls) == 2
    broker.reset_mock()

    # Change to same state should not trigger update in HomeKit
    hass.states.async_set(
        temperature_entity_id,
        30,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.TEMPERATURE,
        },
        force_update=True,
    )
    await hass.async_block_till_done()
    assert acc.char_current_temperature.value == 30
    assert len(broker.mock_calls) == 0

    # Should handle unavailable state, show last known value
    hass.states.async_set(
        humidity_entity_id,
        STATE_UNAVAILABLE,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.HUMIDITY,
        },
    )
    hass.states.async_set(
        pm25_entity_id,
        STATE_UNAVAILABLE,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.PM25,
        },
    )
    hass.states.async_set(
        temperature_entity_id,
        STATE_UNAVAILABLE,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.TEMPERATURE,
        },
    )
    await hass.async_block_till_done()
    assert acc.char_current_humidity.value == 60
    assert acc.char_pm25_density.value == 5
    assert acc.char_air_quality.value == 1
    assert acc.char_current_temperature.value == 30

    # Check that all goes well if we remove the linked sensors
    hass.states.async_remove(humidity_entity_id)
    hass.states.async_remove(pm25_entity_id)
    hass.states.async_remove(temperature_entity_id)
    await hass.async_block_till_done()
    acc.run()
    await hass.async_block_till_done()
    assert len(acc.char_current_humidity.broker.mock_calls) == 0
    assert len(acc.char_pm25_density.broker.mock_calls) == 0
    assert len(acc.char_air_quality.broker.mock_calls) == 0
    assert len(acc.char_current_temperature.broker.mock_calls) == 0

    # HomeKit will show the last known values
    assert acc.char_current_humidity.value == 60
    assert acc.char_pm25_density.value == 5
    assert acc.char_air_quality.value == 1
    assert acc.char_current_temperature.value == 30


async def test_filter_maintenance_linked_sensors(
    hass: HomeAssistant, hk_driver, events: list[Event]
) -> None:
    """Test that a linked filter level and filter change indicator are exposed."""
    entity_id = "fan.demo"
    hass.states.async_set(
        entity_id,
        STATE_ON,
        {
            ATTR_SUPPORTED_FEATURES: FanEntityFeature.SET_SPEED,
        },
    )

    filter_change_indicator_entity_id = "binary_sensor.demo_filter_change_indicator"
    hass.states.async_set(filter_change_indicator_entity_id, STATE_OFF)

    filter_life_level_entity_id = "sensor.demo_filter_life_level"
    hass.states.async_set(filter_life_level_entity_id, 50)

    await hass.async_block_till_done()
    acc = AirPurifier(
        hass,
        hk_driver,
        "Air Purifier",
        entity_id,
        1,
        {
            CONF_LINKED_FILTER_CHANGE_INDICATION: filter_change_indicator_entity_id,
            CONF_LINKED_FILTER_LIFE_LEVEL: filter_life_level_entity_id,
        },
    )
    hk_driver.add_accessory(acc)

    assert acc.linked_filter_change_indicator_binary_sensor is not None
    assert acc.char_filter_change_indication is not None
    assert acc.linked_filter_life_level_sensor is not None
    assert acc.char_filter_life_level is not None

    acc.run()
    await hass.async_block_till_done()

    assert acc.char_filter_change_indication.value == FILTER_OK
    assert acc.char_filter_life_level.value == 50

    # Updated filter change indicator should reflect in HomeKit
    broker = MagicMock()
    acc.char_filter_change_indication.broker = broker
    hass.states.async_set(filter_change_indicator_entity_id, STATE_ON)
    await hass.async_block_till_done()
    assert acc.char_filter_change_indication.value == FILTER_CHANGE_FILTER
    assert len(broker.mock_calls) == 2
    broker.reset_mock()

    # Change to same state should not trigger update in HomeKit
    hass.states.async_set(
        filter_change_indicator_entity_id, STATE_ON, force_update=True
    )
    await hass.async_block_till_done()
    assert acc.char_filter_change_indication.value == FILTER_CHANGE_FILTER
    assert len(broker.mock_calls) == 0

    # Updated filter life level should reflect in HomeKit
    broker = MagicMock()
    acc.char_filter_life_level.broker = broker
    hass.states.async_set(filter_life_level_entity_id, 25)
    await hass.async_block_till_done()
    assert acc.char_filter_life_level.value == 25
    assert len(broker.mock_calls) == 2
    broker.reset_mock()

    # Change to same state should not trigger update in HomeKit
    hass.states.async_set(filter_life_level_entity_id, 25, force_update=True)
    await hass.async_block_till_done()
    assert acc.char_filter_life_level.value == 25
    assert len(broker.mock_calls) == 0

    # Should handle unavailable state, show last known value
    hass.states.async_set(filter_change_indicator_entity_id, STATE_UNAVAILABLE)
    hass.states.async_set(filter_life_level_entity_id, STATE_UNAVAILABLE)
    await hass.async_block_till_done()
    assert acc.char_filter_change_indication.value == FILTER_CHANGE_FILTER
    assert acc.char_filter_life_level.value == 25

    # Check that all goes well if we remove the linked sensors
    hass.states.async_remove(filter_change_indicator_entity_id)
    hass.states.async_remove(filter_life_level_entity_id)
    await hass.async_block_till_done()
    acc.run()
    await hass.async_block_till_done()
    assert len(acc.char_filter_change_indication.broker.mock_calls) == 0
    assert len(acc.char_filter_life_level.broker.mock_calls) == 0

    # HomeKit will show the last known values
    assert acc.char_filter_change_indication.value == FILTER_CHANGE_FILTER
    assert acc.char_filter_life_level.value == 25


async def test_filter_maintenance_only_change_indicator_sensor(
    hass: HomeAssistant, hk_driver, events: list[Event]
) -> None:
    """Test that a linked filter change indicator is exposed."""
    entity_id = "fan.demo"
    hass.states.async_set(
        entity_id,
        STATE_ON,
        {
            ATTR_SUPPORTED_FEATURES: FanEntityFeature.SET_SPEED,
        },
    )

    filter_change_indicator_entity_id = "binary_sensor.demo_filter_change_indicator"
    hass.states.async_set(filter_change_indicator_entity_id, STATE_OFF)

    await hass.async_block_till_done()
    acc = AirPurifier(
        hass,
        hk_driver,
        "Air Purifier",
        entity_id,
        1,
        {
            CONF_LINKED_FILTER_CHANGE_INDICATION: filter_change_indicator_entity_id,
        },
    )
    hk_driver.add_accessory(acc)

    assert acc.linked_filter_change_indicator_binary_sensor is not None
    assert acc.char_filter_change_indication is not None
    assert acc.linked_filter_life_level_sensor is None

    acc.run()
    await hass.async_block_till_done()

    assert acc.char_filter_change_indication.value == FILTER_OK

    hass.states.async_set(filter_change_indicator_entity_id, STATE_ON)
    await hass.async_block_till_done()
    assert acc.char_filter_change_indication.value == FILTER_CHANGE_FILTER


async def test_filter_life_level_linked_sensors(
    hass: HomeAssistant, hk_driver, events: list[Event]
) -> None:
    """Test that a linked filter life level sensor exposed."""
    entity_id = "fan.demo"
    hass.states.async_set(
        entity_id,
        STATE_ON,
        {
            ATTR_SUPPORTED_FEATURES: FanEntityFeature.SET_SPEED,
        },
    )

    filter_life_level_entity_id = "sensor.demo_filter_life_level"
    hass.states.async_set(filter_life_level_entity_id, 50)

    await hass.async_block_till_done()
    acc = AirPurifier(
        hass,
        hk_driver,
        "Air Purifier",
        entity_id,
        1,
        {
            CONF_LINKED_FILTER_LIFE_LEVEL: filter_life_level_entity_id,
        },
    )
    hk_driver.add_accessory(acc)

    assert acc.linked_filter_change_indicator_binary_sensor is None
    assert (
        acc.char_filter_change_indication is not None
    )  # calculated based on filter life level
    assert acc.linked_filter_life_level_sensor is not None
    assert acc.char_filter_life_level is not None

    acc.run()
    await hass.async_block_till_done()

    assert acc.char_filter_change_indication.value == FILTER_OK
    assert acc.char_filter_life_level.value == 50

    hass.states.async_set(
        filter_life_level_entity_id, THRESHOLD_FILTER_CHANGE_NEEDED - 1
    )
    await hass.async_block_till_done()
    assert acc.char_filter_life_level.value == THRESHOLD_FILTER_CHANGE_NEEDED - 1
    assert acc.char_filter_change_indication.value == FILTER_CHANGE_FILTER
