"""Test the Z-Wave JS sensor platform."""

import copy
from datetime import timedelta
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_capture_events,
    async_fire_time_changed,
)
from zwave_js_server.const.command_class.meter import MeterType
from zwave_js_server.event import Event
from zwave_js_server.exceptions import FailedZWaveCommand
from zwave_js_server.model.node import Node

from homeassistant.components.sensor import (
    ATTR_STATE_CLASS,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.components.zwave_js.const import (
    ATTR_METER_TYPE,
    ATTR_METER_TYPE_NAME,
    DOMAIN,
    ZWaveJSService,
    ZWaveJSServiceArgument,
)
from homeassistant.components.zwave_js.helpers import get_valueless_base_unique_id
from homeassistant.components.zwave_js.sensor import (
    CONTROLLER_STATISTICS_KEY_MAP,
    NODE_STATISTICS_KEY_MAP,
)
from homeassistant.config_entries import RELOAD_AFTER_UPDATE_DELAY
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    EVENT_STATE_CHANGED,
    LIGHT_LUX,
    PERCENTAGE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UV_INDEX,
    CommonServiceArgument,
    EntityCategory,
    Platform,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from .common import (
    AIR_TEMPERATURE_SENSOR,
    BATTERY_SENSOR,
    CURRENT_SENSOR,
    ENERGY_SENSOR,
    HUMIDITY_SENSOR,
    POWER_SENSOR,
    VOLTAGE_SENSOR,
)


@pytest.fixture
def platforms() -> list[str]:
    """Fixture to specify platforms to test."""
    return [Platform.SENSOR]


async def test_battery_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ring_keypad: Node,
    integration: MockConfigEntry,
) -> None:
    """Test numeric battery sensors."""
    entity_id = "sensor.keypad_v2_battery_level"
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "100.0"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == PERCENTAGE
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.BATTERY
    assert state.attributes[ATTR_STATE_CLASS] == SensorStateClass.MEASUREMENT

    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry
    assert entity_entry.entity_category is EntityCategory.DIAGNOSTIC

    disabled_sensor_battery_entities = (
        "sensor.keypad_v2_chargingstatus",
        "sensor.keypad_v2_maximum_capacity",
        "sensor.keypad_v2_rechargeorreplace",
        "sensor.keypad_v2_temperature",
    )

    for entity_id in disabled_sensor_battery_entities:
        state = hass.states.get(entity_id)
        assert state is None  # disabled by default

        entity_entry = entity_registry.async_get(entity_id)

        assert entity_entry
        assert entity_entry.entity_category is EntityCategory.DIAGNOSTIC
        assert entity_entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION

        entity_registry.async_update_entity(entity_id, disabled_by=None)

    async_fire_time_changed(
        hass,
        dt_util.utcnow() + timedelta(seconds=RELOAD_AFTER_UPDATE_DELAY + 1),
    )
    await hass.async_block_till_done()

    entity_id = "sensor.keypad_v2_chargingstatus"
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "Maintaining"
    assert ATTR_UNIT_OF_MEASUREMENT not in state.attributes
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.ENUM
    assert ATTR_STATE_CLASS not in state.attributes

    entity_id = "sensor.keypad_v2_maximum_capacity"
    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNKNOWN
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == PERCENTAGE
    assert ATTR_DEVICE_CLASS not in state.attributes
    assert state.attributes[ATTR_STATE_CLASS] == SensorStateClass.MEASUREMENT

    entity_id = "sensor.keypad_v2_rechargeorreplace"
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "No"
    assert ATTR_UNIT_OF_MEASUREMENT not in state.attributes
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.ENUM
    assert ATTR_STATE_CLASS not in state.attributes

    entity_id = "sensor.keypad_v2_temperature"
    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNKNOWN
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfTemperature.CELSIUS
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.TEMPERATURE
    assert state.attributes[ATTR_STATE_CLASS] == SensorStateClass.MEASUREMENT


async def test_numeric_sensor(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    multisensor_6,
    express_controls_ezmultipli,
    integration,
) -> None:
    """Test the numeric sensor."""
    state = hass.states.get(AIR_TEMPERATURE_SENSOR)

    assert state
    assert state.state == "9.0"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfTemperature.CELSIUS
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.TEMPERATURE
    assert state.attributes[ATTR_STATE_CLASS] == SensorStateClass.MEASUREMENT

    state = hass.states.get(BATTERY_SENSOR)

    assert state
    assert state.state == "100.0"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == PERCENTAGE
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.BATTERY
    assert state.attributes[ATTR_STATE_CLASS] == SensorStateClass.MEASUREMENT

    entity_entry = entity_registry.async_get(BATTERY_SENSOR)
    assert entity_entry
    assert entity_entry.entity_category is EntityCategory.DIAGNOSTIC

    state = hass.states.get(HUMIDITY_SENSOR)

    assert state
    assert state.state == "65.0"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == PERCENTAGE
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.HUMIDITY
    assert state.attributes[ATTR_STATE_CLASS] == SensorStateClass.MEASUREMENT

    state = hass.states.get("sensor.multisensor_6_ultraviolet")

    assert state
    assert state.state == "0.0"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UV_INDEX
    assert ATTR_DEVICE_CLASS not in state.attributes
    assert state.attributes[ATTR_STATE_CLASS] == SensorStateClass.MEASUREMENT

    state = hass.states.get("sensor.multisensor_6_illuminance")

    assert state
    assert state.state == "0.0"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == LIGHT_LUX
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.ILLUMINANCE
    assert state.attributes[ATTR_STATE_CLASS] == SensorStateClass.MEASUREMENT

    state = hass.states.get("sensor.basement_hsm200_illuminance")

    assert state
    assert state.state == "61.0"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == PERCENTAGE
    assert ATTR_DEVICE_CLASS not in state.attributes
    assert state.attributes[ATTR_STATE_CLASS] == SensorStateClass.MEASUREMENT

    event = Event(
        "value updated",
        {
            "source": "node",
            "event": "value updated",
            "nodeId": express_controls_ezmultipli.node_id,
            "args": {
                "commandClassName": "Multilevel Sensor",
                "commandClass": 49,
                "endpoint": 0,
                "property": "Illuminance",
                "propertyName": "Illuminance",
                "newValue": None,
                "prevValue": 61,
            },
        },
    )

    express_controls_ezmultipli.receive_event(event)
    await hass.async_block_till_done()
    state = hass.states.get("sensor.basement_hsm200_illuminance")
    assert state
    assert state.state == STATE_UNKNOWN


@pytest.mark.parametrize(
    (
        "property_",
        "entity_id",
        "old_scale",
        "old_unit",
        "new_scale",
        "new_unit",
        "unit_of_measurement",
    ),
    [
        pytest.param(
            "Humidity",
            HUMIDITY_SENSOR,
            1,
            "g/m³",
            0,
            "%",
            PERCENTAGE,
            id="humidity",
        ),
        pytest.param(
            "Illuminance",
            "sensor.multisensor_6_illuminance",
            0,
            "%",
            1,
            "Lux",
            LIGHT_LUX,
            id="illuminance",
        ),
    ],
)
@pytest.mark.usefixtures("integration")
async def test_legacy_multilevel_sensor_scale_change(
    hass: HomeAssistant,
    client: MagicMock,
    multisensor_6_state: dict[str, Any],
    property_: str,
    entity_id: str,
    old_scale: int,
    old_unit: str,
    new_scale: int,
    new_unit: str,
    unit_of_measurement: str,
) -> None:
    """Test a legacy multilevel sensor that changes to a migrated scale."""
    node_state = copy.deepcopy(multisensor_6_state)
    value = next(
        value
        for value in node_state["values"]
        if value["commandClass"] == 49 and value["property"] == property_
    )
    value["metadata"]["ccSpecific"]["scale"] = old_scale
    value["metadata"]["unit"] = old_unit
    sensor_type = value["metadata"]["ccSpecific"]["sensorType"]

    event = Event(
        "node added",
        {
            "source": "controller",
            "event": "node added",
            "node": node_state,
            "result": {},
        },
    )
    client.driver.controller.receive_event(event)
    await hass.async_block_till_done()
    node = client.driver.controller.nodes[node_state["nodeId"]]

    state = hass.states.get(entity_id)
    assert state
    assert ATTR_DEVICE_CLASS not in state.attributes
    assert state.attributes[ATTR_STATE_CLASS] == SensorStateClass.MEASUREMENT
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == old_unit

    event = Event(
        "metadata updated",
        {
            "source": "node",
            "event": "metadata updated",
            "nodeId": node.node_id,
            "args": {
                "commandClassName": "Multilevel Sensor",
                "commandClass": 49,
                "endpoint": 0,
                "property": property_,
                "metadata": {
                    "type": "number",
                    "readable": True,
                    "writeable": False,
                    "label": property_,
                    "ccSpecific": {"sensorType": sensor_type, "scale": new_scale},
                    "unit": new_unit,
                },
                "propertyName": property_,
                "nodeId": node.node_id,
            },
        },
    )
    node.receive_event(event)
    event = Event(
        "value updated",
        {
            "source": "node",
            "event": "value updated",
            "nodeId": node.node_id,
            "args": {
                "commandClassName": "Multilevel Sensor",
                "commandClass": 49,
                "endpoint": 0,
                "property": property_,
                "newValue": 50,
                "prevValue": value["value"],
                "propertyName": property_,
            },
        },
    )
    node.receive_event(event)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "50.0"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == unit_of_measurement
    # The cached device class is not updated by the in-place description swap.
    assert ATTR_DEVICE_CLASS not in state.attributes


async def test_invalid_multilevel_sensor_scale(
    hass: HomeAssistant, client, multisensor_6_state, integration
) -> None:
    """Test a multilevel sensor with an invalid scale."""
    node_state = copy.deepcopy(multisensor_6_state)
    value = next(
        value
        for value in node_state["values"]
        if value["commandClass"] == 49 and value["property"] == "Air temperature"
    )
    value["metadata"]["ccSpecific"]["scale"] = -1
    value["metadata"]["unit"] = None

    event = Event(
        "node added",
        {
            "source": "controller",
            "event": "node added",
            "node": node_state,
            "result": {},
        },
    )
    client.driver.controller.receive_event(event)
    await hass.async_block_till_done()

    state = hass.states.get(AIR_TEMPERATURE_SENSOR)

    assert state
    assert state.state == "9.0"
    assert ATTR_UNIT_OF_MEASUREMENT not in state.attributes
    assert ATTR_DEVICE_CLASS not in state.attributes
    assert ATTR_STATE_CLASS not in state.attributes


async def test_energy_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    hank_binary_switch,
    integration,
) -> None:
    """Test power and energy sensors."""
    state = hass.states.get(POWER_SENSOR)

    assert state
    assert state.state == "0.0"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfPower.WATT
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.POWER
    assert state.attributes[ATTR_STATE_CLASS] is SensorStateClass.MEASUREMENT

    state = hass.states.get(ENERGY_SENSOR)

    assert state
    assert state.state == "0.164"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfEnergy.KILO_WATT_HOUR
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.ENERGY
    assert state.attributes[ATTR_STATE_CLASS] is SensorStateClass.TOTAL_INCREASING

    state = hass.states.get(VOLTAGE_SENSOR)

    assert state
    assert state.state == "122.963"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfElectricPotential.VOLT
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.VOLTAGE

    entity_entry = entity_registry.async_get(VOLTAGE_SENSOR)

    assert entity_entry is not None
    sensor_options = entity_entry.options.get("sensor")
    assert sensor_options is not None
    assert sensor_options["suggested_display_precision"] == 0

    state = hass.states.get(CURRENT_SENSOR)

    assert state
    assert state.state == "0.0"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfElectricCurrent.AMPERE
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.CURRENT


async def test_basic_cc_sensor(
    hass: HomeAssistant, client, basic_cc_sensor, integration
) -> None:
    """Test a Basic CC sensor gets discovered correctly."""
    state = hass.states.get("sensor.foo_basic")
    assert state is not None
    assert state.state == "255.0"


async def test_config_parameter_sensor(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    climate_adc_t3000,
    lock_id_lock_as_id150,
    integration,
) -> None:
    """Test config parameter sensor is created."""
    sensor_entity_id = "sensor.adc_t3000_system_configuration_cool_stages"
    sensor_with_states_entity_id = "sensor.adc_t3000_power_source"
    for entity_id in (sensor_entity_id, sensor_with_states_entity_id):
        entity_entry = entity_registry.async_get(entity_id)
        assert entity_entry
        assert entity_entry.disabled
        assert entity_entry.entity_category == EntityCategory.DIAGNOSTIC

    for entity_id in (sensor_entity_id, sensor_with_states_entity_id):
        updated_entry = entity_registry.async_update_entity(entity_id, disabled_by=None)
        assert updated_entry != entity_entry
        assert updated_entry.disabled is False

    # reload integration and check if entity is correctly there
    await hass.config_entries.async_reload(integration.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(sensor_entity_id)
    assert state
    assert state.state == "1"

    state = hass.states.get(sensor_with_states_entity_id)
    assert state
    assert state.state == "C-Wire"

    updated_entry = entity_registry.async_update_entity(
        entity_entry.entity_id, disabled_by=None
    )
    assert updated_entry != entity_entry
    assert updated_entry.disabled is False

    # reload integration and check if entity is correctly there
    await hass.config_entries.async_reload(integration.entry_id)
    await hass.async_block_till_done()


async def test_controller_status_sensor(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, client, integration
) -> None:
    """Test controller status sensor updates on state changes."""
    entity_id = "sensor.z_stick_gen5_usb_controller_status"
    entity_entry = entity_registry.async_get(entity_id)

    assert not entity_entry.disabled
    assert entity_entry.entity_category is EntityCategory.DIAGNOSTIC
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "ready"

    event = Event(
        "status changed",
        data={"source": "controller", "event": "status changed", "status": 1},
    )
    client.driver.controller.receive_event(event)
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "unresponsive"

    # Test transitions work
    event = Event(
        "status changed",
        data={"source": "controller", "event": "status changed", "status": 2},
    )
    client.driver.controller.receive_event(event)
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "jammed"

    # Disconnect the client and make sure the entity is still available
    await client.disconnect()
    assert hass.states.get(entity_id).state != STATE_UNAVAILABLE


async def test_node_status_sensor(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    client,
    lock_id_lock_as_id150,
    integration,
) -> None:
    """Test node status sensor is created and gets updated on node state changes."""
    node_status_entity_id = "sensor.z_wave_module_for_id_lock_150_and_101_node_status"
    node = lock_id_lock_as_id150
    entity_entry = entity_registry.async_get(node_status_entity_id)

    assert not entity_entry.disabled
    assert entity_entry.entity_category is EntityCategory.DIAGNOSTIC
    assert hass.states.get(node_status_entity_id).state == "alive"

    # Test transitions work
    event = Event(
        "dead", data={"source": "node", "event": "dead", "nodeId": node.node_id}
    )
    node.receive_event(event)
    assert hass.states.get(node_status_entity_id).state == "dead"

    event = Event(
        "wake up", data={"source": "node", "event": "wake up", "nodeId": node.node_id}
    )
    node.receive_event(event)
    assert hass.states.get(node_status_entity_id).state == "awake"

    event = Event(
        "sleep", data={"source": "node", "event": "sleep", "nodeId": node.node_id}
    )
    node.receive_event(event)
    assert hass.states.get(node_status_entity_id).state == "asleep"

    event = Event(
        "alive", data={"source": "node", "event": "alive", "nodeId": node.node_id}
    )
    node.receive_event(event)
    assert hass.states.get(node_status_entity_id).state == "alive"

    # Disconnect the client and make sure the entity is still available
    await client.disconnect()
    assert hass.states.get(node_status_entity_id).state != STATE_UNAVAILABLE

    # Assert a node status sensor entity is not created for the controller
    driver = client.driver
    controller_node = driver.controller.nodes[1]
    assert controller_node.is_controller_node
    assert (
        entity_registry.async_get_entity_id(
            "sensor",
            DOMAIN,
            f"{get_valueless_base_unique_id(driver, controller_node)}.node_status",
        )
        is None
    )

    # Assert a controller status sensor entity is not created for a node
    assert not node.is_controller_node
    assert (
        entity_registry.async_get_entity_id(
            "sensor",
            DOMAIN,
            f"{get_valueless_base_unique_id(driver, node)}.controller_status",
        )
        is None
    )


async def test_node_status_sensor_not_ready(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    client,
    lock_id_lock_as_id150_not_ready,
    lock_id_lock_as_id150_state,
    integration,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test node status sensor is created and available if node is not ready."""
    node_status_entity_id = "sensor.z_wave_module_for_id_lock_150_and_101_node_status"
    node = lock_id_lock_as_id150_not_ready
    assert not node.ready
    entity_entry = entity_registry.async_get(node_status_entity_id)

    assert not entity_entry.disabled
    assert hass.states.get(node_status_entity_id)
    assert hass.states.get(node_status_entity_id).state == "alive"

    # Mark node as ready
    event = Event(
        "ready",
        {
            "source": "node",
            "event": "ready",
            "nodeId": node.node_id,
            "nodeState": lock_id_lock_as_id150_state,
        },
    )
    node.receive_event(event)
    assert node.ready
    assert hass.states.get(node_status_entity_id)
    assert hass.states.get(node_status_entity_id).state == "alive"

    await hass.services.async_call(
        DOMAIN,
        ZWaveJSService.REFRESH_VALUE,
        {
            CommonServiceArgument.ENTITY_ID: node_status_entity_id,
        },
        blocking=True,
    )
    await hass.async_block_till_done()
    assert f"There is no value to refresh for {node_status_entity_id}" in caplog.text


@pytest.mark.parametrize(
    "entity_id",
    [
        "sensor.smart_switch_6_electric_consumed_kwh",
        "sensor.smart_switch_6_electric_consumed_a",
    ],
)
async def test_reset_meter(
    hass: HomeAssistant,
    client,
    aeon_smart_switch_6,
    integration,
    entity_id: str,
) -> None:
    """Test reset_meter service."""
    client.async_send_command.return_value = {}
    client.async_send_command_no_wait.return_value = {}

    # Test successful meter reset call
    await hass.services.async_call(
        DOMAIN,
        ZWaveJSService.RESET_METER,
        {
            CommonServiceArgument.ENTITY_ID: entity_id,
        },
        blocking=True,
    )

    assert len(client.async_send_command_no_wait.call_args_list) == 1
    args = client.async_send_command_no_wait.call_args[0][0]
    assert args["command"] == "endpoint.invoke_cc_api"
    assert args["nodeId"] == aeon_smart_switch_6.node_id
    assert args["endpoint"] == 0
    assert args["args"] == []

    client.async_send_command_no_wait.reset_mock()

    # Test successful meter reset call with options
    await hass.services.async_call(
        DOMAIN,
        ZWaveJSService.RESET_METER,
        {
            CommonServiceArgument.ENTITY_ID: entity_id,
            ZWaveJSServiceArgument.METER_TYPE: 1,
            ZWaveJSServiceArgument.VALUE: 2,
        },
        blocking=True,
    )

    assert len(client.async_send_command_no_wait.call_args_list) == 1
    args = client.async_send_command_no_wait.call_args[0][0]
    assert args["command"] == "endpoint.invoke_cc_api"
    assert args["nodeId"] == aeon_smart_switch_6.node_id
    assert args["endpoint"] == 0
    assert args["args"] == [{"type": 1, "targetValue": 2}]

    client.async_send_command_no_wait.reset_mock()

    client.async_send_command_no_wait.side_effect = FailedZWaveCommand(
        "test", 1, "test"
    )

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            DOMAIN,
            ZWaveJSService.RESET_METER,
            {CommonServiceArgument.ENTITY_ID: entity_id},
            blocking=True,
        )

    assert str(err.value) == (
        "Failed to reset meters on node Node(node_id=102) endpoint 0: "
        "zwave_error: Z-Wave error 1 - test"
    )


@pytest.mark.parametrize(
    ("entity_id", "device_class", "state_class", "unit_of_measurement"),
    [
        (
            "sensor.smart_switch_6_electric_consumed_kwh",
            SensorDeviceClass.ENERGY,
            SensorStateClass.TOTAL_INCREASING,
            UnitOfEnergy.KILO_WATT_HOUR,
        ),
        (
            "sensor.smart_switch_6_electric_consumed_a",
            SensorDeviceClass.CURRENT,
            SensorStateClass.MEASUREMENT,
            UnitOfElectricCurrent.AMPERE,
        ),
    ],
)
async def test_meter_attributes(
    hass: HomeAssistant,
    client,
    aeon_smart_switch_6,
    integration,
    entity_id: str,
    device_class: SensorDeviceClass,
    state_class: SensorStateClass,
    unit_of_measurement: str,
) -> None:
    """Test meter entity attributes."""
    state = hass.states.get(entity_id)
    assert state
    assert state.attributes[ATTR_METER_TYPE] == MeterType.ELECTRIC.value
    assert state.attributes[ATTR_METER_TYPE_NAME] == MeterType.ELECTRIC.name
    assert state.attributes[ATTR_DEVICE_CLASS] == device_class
    assert state.attributes[ATTR_STATE_CLASS] is state_class
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == unit_of_measurement


@pytest.mark.parametrize(
    ("entity_id", "property_key_name"),
    [
        ("sensor.smart_switch_6_electric_consumed_kwh", "Electric_kWh_Consumed"),
        ("sensor.smart_switch_6_electric_consumed_a", "Electric_A_Consumed"),
    ],
)
async def test_invalid_meter_scale(
    hass: HomeAssistant,
    client,
    aeon_smart_switch_6_state,
    integration,
    entity_id: str,
    property_key_name: str,
) -> None:
    """Test a meter sensor with an invalid scale."""
    node_state = copy.deepcopy(aeon_smart_switch_6_state)
    value = next(
        value
        for value in node_state["values"]
        if value["commandClass"] == 50
        and value["property"] == "value"
        and value["propertyKeyName"] == property_key_name
    )
    value["metadata"]["ccSpecific"]["scale"] = -1
    value["metadata"]["unit"] = None

    event = Event(
        "node added",
        {
            "source": "controller",
            "event": "node added",
            "node": node_state,
            "result": {},
        },
    )
    client.driver.controller.receive_event(event)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.attributes[ATTR_METER_TYPE] == MeterType.ELECTRIC.value
    assert state.attributes[ATTR_METER_TYPE_NAME] == MeterType.ELECTRIC.name
    assert ATTR_DEVICE_CLASS not in state.attributes
    assert ATTR_STATE_CLASS not in state.attributes
    assert ATTR_UNIT_OF_MEASUREMENT not in state.attributes


async def test_special_meters(
    hass: HomeAssistant, aeon_smart_switch_6_state, client, integration
) -> None:
    """Test meters that have special handling."""
    node_data = copy.deepcopy(
        aeon_smart_switch_6_state
    )  # Copy to allow modification in tests.
    # Add an ElectricScale.KILOVOLT_AMPERE_HOUR value to the state so we can test that
    # it is handled differently (no device class)
    node_data["values"].append(
        {
            "endpoint": 10,
            "commandClass": 50,
            "commandClassName": "Meter",
            "property": "value",
            "propertyKey": 65537,
            "propertyName": "value",
            "propertyKeyName": "Electric_kVah_Consumed",
            "ccVersion": 3,
            "metadata": {
                "type": "number",
                "readable": True,
                "writeable": False,
                "label": "Electric Consumed [kVah]",
                "unit": "kVah",
                "ccSpecific": {"meterType": 1, "rateType": 1, "scale": 1},
            },
            "value": 659.813,
        },
    )
    node_data["endpoints"].append(
        {
            "nodeId": 102,
            "index": 10,
            "installerIcon": 1792,
            "userIcon": 1792,
            "commandClasses": [
                {"id": 50, "name": "Meter", "version": 3, "isSecure": False}
            ],
        }
    )
    # Add an ElectricScale.KILOVOLT_AMPERE_REACTIVE value to test
    # that it is handled differently (no device class)
    node_data["values"].append(
        {
            "endpoint": 11,
            "commandClass": 50,
            "commandClassName": "Meter",
            "property": "value",
            "propertyKey": 65537,
            "propertyName": "value",
            "propertyKeyName": "Electric_kVa_reactive_Consumed",
            "ccVersion": 3,
            "metadata": {
                "type": "number",
                "readable": True,
                "writeable": False,
                "label": "Electric Consumed [kVa reactive]",
                "unit": "kVa reactive",
                "ccSpecific": {"meterType": 1, "rateType": 1, "scale": 7},
            },
            "value": 659.813,
        },
    )
    node_data["endpoints"].append(
        {
            "nodeId": 102,
            "index": 11,
            "installerIcon": 1792,
            "userIcon": 1792,
            "commandClasses": [
                {"id": 50, "name": "Meter", "version": 3, "isSecure": False}
            ],
        }
    )
    node = Node(client, node_data)
    event = {"node": node}
    client.driver.controller.emit("node added", event)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.smart_switch_6_electric_consumed_kvah_10")
    assert state
    assert ATTR_DEVICE_CLASS not in state.attributes
    assert state.attributes[ATTR_STATE_CLASS] is SensorStateClass.TOTAL_INCREASING

    state = hass.states.get("sensor.smart_switch_6_electric_consumed_kva_reactive_11")
    assert state
    assert ATTR_DEVICE_CLASS not in state.attributes
    assert state.attributes[ATTR_STATE_CLASS] is SensorStateClass.MEASUREMENT


async def test_unit_change(hass: HomeAssistant, zp3111, client, integration) -> None:
    """Test unit change via metadata updated event is handled by numeric sensors."""
    entity_id = "sensor.4_in_1_sensor_air_temperature"
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "21.98"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfTemperature.CELSIUS
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.TEMPERATURE
    event = Event(
        "metadata updated",
        {
            "source": "node",
            "event": "metadata updated",
            "nodeId": zp3111.node_id,
            "args": {
                "commandClassName": "Multilevel Sensor",
                "commandClass": 49,
                "endpoint": 0,
                "property": "Air temperature",
                "metadata": {
                    "type": "number",
                    "readable": True,
                    "writeable": False,
                    "label": "Air temperature",
                    "ccSpecific": {"sensorType": 1, "scale": 1},
                    "unit": "°F",
                },
                "propertyName": "Air temperature",
                "nodeId": zp3111.node_id,
            },
        },
    )
    zp3111.receive_event(event)
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "21.98"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfTemperature.CELSIUS
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.TEMPERATURE
    event = Event(
        "value updated",
        {
            "source": "node",
            "event": "value updated",
            "nodeId": zp3111.node_id,
            "args": {
                "commandClassName": "Multilevel Sensor",
                "commandClass": 49,
                "endpoint": 0,
                "property": "Air temperature",
                "newValue": 212,
                "prevValue": 21.98,
                "propertyName": "Air temperature",
            },
        },
    )
    zp3111.receive_event(event)
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "100.0"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfTemperature.CELSIUS
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.TEMPERATURE


def _air_temperature_metadata_updated_event(
    node: Node, scale: int, unit: str | None
) -> Event:
    """Return a metadata updated event for the air temperature value."""
    return Event(
        "metadata updated",
        {
            "source": "node",
            "event": "metadata updated",
            "nodeId": node.node_id,
            "args": {
                "commandClassName": "Multilevel Sensor",
                "commandClass": 49,
                "endpoint": 0,
                "property": "Air temperature",
                "metadata": {
                    "type": "number",
                    "readable": True,
                    "writeable": False,
                    "label": "Air temperature",
                    "ccSpecific": {"sensorType": 1, "scale": scale},
                    "unit": unit,
                },
                "propertyName": "Air temperature",
                "nodeId": node.node_id,
            },
        },
    )


def _air_temperature_value_updated_event(
    node: Node, new_value: float, prev_value: float
) -> Event:
    """Return a value updated event for the air temperature value."""
    return Event(
        "value updated",
        {
            "source": "node",
            "event": "value updated",
            "nodeId": node.node_id,
            "args": {
                "commandClassName": "Multilevel Sensor",
                "commandClass": 49,
                "endpoint": 0,
                "property": "Air temperature",
                "newValue": new_value,
                "prevValue": prev_value,
                "propertyName": "Air temperature",
            },
        },
    )


@pytest.mark.parametrize(
    ("scale", "unit", "expected_state", "expected_unit"),
    [
        # The metric test unit system converts the native °F to °C: 68 °F is 20 °C.
        pytest.param(1, "°F", "20.0", UnitOfTemperature.CELSIUS, id="fahrenheit"),
        # An invalid scale makes _get_scale_type catch UnknownValueData and return
        # None, and the value is rediscovered as a numeric sensor without a unit.
        pytest.param(255, None, "68.0", None, id="invalid_scale"),
    ],
)
async def test_new_sensor_scale_change_rediscovers_entity(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    client: MagicMock,
    multisensor_6: Node,
    integration: MockConfigEntry,
    scale: int,
    unit: str | None,
    expected_state: str,
    expected_unit: str | None,
) -> None:
    """Test a scale change rediscovers the new-style sensor without a reload."""
    entity_id = AIR_TEMPERATURE_SENSOR
    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "9.0"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfTemperature.CELSIUS
    state_changed_events = async_capture_events(hass, EVENT_STATE_CHANGED)

    # Let a scheduled reload run, so other entities would become unavailable.
    with patch.object(
        hass.config_entries,
        "async_schedule_reload",
        wraps=hass.config_entries.async_schedule_reload,
    ) as mock_schedule_reload:
        multisensor_6.receive_event(
            _air_temperature_metadata_updated_event(multisensor_6, scale, unit)
        )
        await hass.async_block_till_done()
        # Rediscovery waits for the value update that follows the metadata update.
        state = hass.states.get(entity_id)
        assert state
        assert state.state == "9.0"
        multisensor_6.receive_event(
            _air_temperature_value_updated_event(multisensor_6, 68, 9)
        )
        await hass.async_block_till_done()

    mock_schedule_reload.assert_not_called()
    client.disconnect.assert_not_called()
    new_entity_entry = entity_registry.async_get(entity_id)
    assert new_entity_entry
    assert new_entity_entry.id == entity_entry.id
    state = hass.states.get(entity_id)
    assert state
    assert state.state == expected_state
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == expected_unit
    # Neither the old value in the new scale nor the new value in the old scale
    # is reported in between.
    assert [
        event.data["new_state"].state
        for event in state_changed_events
        if event.data["entity_id"] == entity_id
    ] == [STATE_UNAVAILABLE, expected_state]
    assert not [
        event.data["entity_id"]
        for event in state_changed_events
        if event.data["entity_id"] != entity_id
        and event.data["new_state"].state == STATE_UNAVAILABLE
    ]


async def test_new_sensor_no_rediscovery_without_scale_change(
    hass: HomeAssistant,
    multisensor_6: Node,
    integration: MockConfigEntry,
) -> None:
    """Test the new-style sensor is not rediscovered when the scale is unchanged."""
    entity_id = AIR_TEMPERATURE_SENSOR
    state_changed_events = async_capture_events(hass, EVENT_STATE_CHANGED)

    with patch.object(
        hass.config_entries, "async_schedule_reload"
    ) as mock_schedule_reload:
        multisensor_6.receive_event(
            _air_temperature_metadata_updated_event(multisensor_6, 0, "°C")
        )
        await hass.async_block_till_done()
        multisensor_6.receive_event(
            _air_temperature_value_updated_event(multisensor_6, 20, 9)
        )
        await hass.async_block_till_done()

    # Removing the entity for rediscovery would write an unavailable state in between.
    assert [
        event.data["new_state"].state
        for event in state_changed_events
        if event.data["entity_id"] == entity_id
    ] == ["20.0"]
    mock_schedule_reload.assert_not_called()
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "20.0"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfTemperature.CELSIUS


CONTROLLER_STATISTICS_ENTITY_PREFIX = "sensor.z_stick_gen5_usb_controller_"
# controller statistics with initial state of 0
CONTROLLER_STATISTICS_SUFFIXES = {
    "successful_messages_tx": 1,
    "successful_messages_rx": 2,
    "messages_dropped_tx": 3,
    "messages_dropped_rx": 4,
    "messages_not_accepted": 5,
    "collisions": 6,
    "missing_acks": 7,
    "timed_out_responses": 8,
    "timed_out_callbacks": 9,
}
# controller statistics with initial state of unknown
CONTROLLER_STATISTICS_SUFFIXES_UNKNOWN = {
    "signal_noise_channel_0": -1,
    "avg_signal_noise_channel_0": -2,
    "signal_noise_channel_1": -3,
    "avg_signal_noise_channel_1": -4,
    "signal_noise_channel_2": -5,
    "avg_signal_noise_channel_2": -6,
    "signal_noise_channel_3": STATE_UNKNOWN,
    "avg_signal_noise_channel_3": STATE_UNKNOWN,
}
NODE_STATISTICS_ENTITY_PREFIX = "sensor.4_in_1_sensor_"
# node statistics with initial state of 0
NODE_STATISTICS_SUFFIXES = {
    "successful_commands_tx": 1,
    "successful_commands_rx": 2,
    "commands_dropped_tx": 3,
    "commands_dropped_rx": 4,
    "timed_out_responses": 5,
}
# node statistics with initial state of unknown
NODE_STATISTICS_SUFFIXES_UNKNOWN = {
    "round_trip_time": 6,
    "signal_strength": 7,
}


async def test_statistics_sensors_migration(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    zp3111_state,
    client,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test statistics migration sensor."""
    node = Node(client, copy.deepcopy(zp3111_state))
    client.driver.controller.nodes[node.node_id] = node

    entry = MockConfigEntry(domain=DOMAIN, data={"url": "ws://test.org"})
    entry.add_to_hass(hass)

    controller_base_unique_id = f"{client.driver.controller.home_id}.1.statistics"
    node_base_unique_id = f"{client.driver.controller.home_id}.22.statistics"

    # Create entity registry records for the old statistics keys
    for base_unique_id, key_map in (
        (controller_base_unique_id, CONTROLLER_STATISTICS_KEY_MAP),
        (node_base_unique_id, NODE_STATISTICS_KEY_MAP),
    ):
        # old key
        for key in key_map.values():
            entity_registry.async_get_or_create(
                "sensor", DOMAIN, f"{base_unique_id}_{key}"
            )

    # Set up integration
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Validate that entity unique ID's have changed
    for base_unique_id, key_map in (
        (controller_base_unique_id, CONTROLLER_STATISTICS_KEY_MAP),
        (node_base_unique_id, NODE_STATISTICS_KEY_MAP),
    ):
        for new_key, old_key in key_map.items():
            # If the key has changed, the old entity should not exist
            if new_key != old_key:
                assert not entity_registry.async_get_entity_id(
                    "sensor", DOMAIN, f"{base_unique_id}_{old_key}"
                )
            assert entity_registry.async_get_entity_id(
                "sensor", DOMAIN, f"{base_unique_id}_{new_key}"
            )


async def test_statistics_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    zp3111,
    client,
    integration,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test statistics sensors."""

    for prefix, suffixes in (
        (CONTROLLER_STATISTICS_ENTITY_PREFIX, CONTROLLER_STATISTICS_SUFFIXES),
        (CONTROLLER_STATISTICS_ENTITY_PREFIX, CONTROLLER_STATISTICS_SUFFIXES_UNKNOWN),
        (NODE_STATISTICS_ENTITY_PREFIX, NODE_STATISTICS_SUFFIXES),
        (NODE_STATISTICS_ENTITY_PREFIX, NODE_STATISTICS_SUFFIXES_UNKNOWN),
    ):
        for suffix_key in suffixes:
            entry = entity_registry.async_get(f"{prefix}{suffix_key}")
            assert entry, f"Entity {prefix}{suffix_key} not found"
            assert entry.disabled
            assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION

            entity_registry.async_update_entity(entry.entity_id, disabled_by=None)

    # reload integration and check if entity is correctly there
    await hass.config_entries.async_reload(integration.entry_id)
    await hass.async_block_till_done()

    for prefix, suffixes, initial_state in (
        (CONTROLLER_STATISTICS_ENTITY_PREFIX, CONTROLLER_STATISTICS_SUFFIXES, "0"),
        (
            CONTROLLER_STATISTICS_ENTITY_PREFIX,
            CONTROLLER_STATISTICS_SUFFIXES_UNKNOWN,
            STATE_UNKNOWN,
        ),
        (NODE_STATISTICS_ENTITY_PREFIX, NODE_STATISTICS_SUFFIXES, "0"),
        (
            NODE_STATISTICS_ENTITY_PREFIX,
            NODE_STATISTICS_SUFFIXES_UNKNOWN,
            STATE_UNKNOWN,
        ),
    ):
        for suffix_key in suffixes:
            entry = entity_registry.async_get(f"{prefix}{suffix_key}")
            assert entry, f"Entity {prefix}{suffix_key} not found"
            assert not entry.disabled
            assert entry.disabled_by is None

            state = hass.states.get(entry.entity_id)
            assert state, f"State for {entry.entity_id} not found"
            assert state.state == initial_state

    # Fire statistics updated for controller
    event = Event(
        "statistics updated",
        {
            "source": "controller",
            "event": "statistics updated",
            "statistics": {
                "messagesTX": 1,
                "messagesRX": 2,
                "messagesDroppedTX": 3,
                "messagesDroppedRX": 4,
                "NAK": 5,
                "CAN": 6,
                "timeoutACK": 7,
                "timeoutResponse": 8,
                "timeoutCallback": 9,
                "backgroundRSSI": {
                    "channel0": {
                        "current": -1,
                        "average": -2,
                    },
                    "channel1": {
                        "current": -3,
                        "average": -4,
                    },
                    "channel2": {
                        "current": -5,
                        "average": -6,
                    },
                    "timestamp": 1681967176510,
                },
            },
        },
    )
    client.driver.controller.receive_event(event)

    # Fire statistics updated event for node
    event = Event(
        "statistics updated",
        {
            "source": "node",
            "event": "statistics updated",
            "nodeId": zp3111.node_id,
            "statistics": {
                "commandsTX": 1,
                "commandsRX": 2,
                "commandsDroppedTX": 3,
                "commandsDroppedRX": 4,
                "timeoutResponse": 5,
                "rtt": 6,
                "rssi": 7,
                "lwr": {
                    "protocolDataRate": 1,
                    "rssi": 1,
                    "repeaters": [],
                    "repeaterRSSI": [],
                    "routeFailedBetween": [],
                },
                "nlwr": {
                    "protocolDataRate": 2,
                    "rssi": 2,
                    "repeaters": [],
                    "repeaterRSSI": [],
                    "routeFailedBetween": [],
                },
                "lastSeen": "2024-01-01T00:00:00+0000",
            },
        },
    )
    zp3111.receive_event(event)

    # Check that states match the statistics from the updates
    for prefix, suffixes in (
        (CONTROLLER_STATISTICS_ENTITY_PREFIX, CONTROLLER_STATISTICS_SUFFIXES),
        (CONTROLLER_STATISTICS_ENTITY_PREFIX, CONTROLLER_STATISTICS_SUFFIXES_UNKNOWN),
        (NODE_STATISTICS_ENTITY_PREFIX, NODE_STATISTICS_SUFFIXES),
        (NODE_STATISTICS_ENTITY_PREFIX, NODE_STATISTICS_SUFFIXES_UNKNOWN),
    ):
        for suffix_key, val in suffixes.items():
            entity_id = f"{prefix}{suffix_key}"
            state = hass.states.get(entity_id)
            assert state
            assert state.state == str(val)

            await hass.services.async_call(
                DOMAIN,
                ZWaveJSService.REFRESH_VALUE,
                {CommonServiceArgument.ENTITY_ID: entity_id},
                blocking=True,
            )
    await hass.async_block_till_done()
    assert caplog.text.count("There is no value to refresh for") == len(
        [
            *CONTROLLER_STATISTICS_SUFFIXES,
            *CONTROLLER_STATISTICS_SUFFIXES_UNKNOWN,
            *NODE_STATISTICS_SUFFIXES,
            *NODE_STATISTICS_SUFFIXES_UNKNOWN,
        ]
    )


async def test_last_seen_statistics_sensors(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, zp3111, client, integration
) -> None:
    """Test last_seen statistics sensors."""
    entity_id = f"{NODE_STATISTICS_ENTITY_PREFIX}last_seen"
    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.disabled
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    assert hass.states.get(entity_id) is None  # disabled by default

    entity_registry.async_update_entity(entity_id, disabled_by=None)
    async_fire_time_changed(
        hass,
        dt_util.utcnow() + timedelta(seconds=RELOAD_AFTER_UPDATE_DELAY + 1),
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "2024-01-01T12:00:00+00:00"


async def test_rssi_sensor_error(
    hass: HomeAssistant,
    zp3111: Node,
    integration: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test rssi sensor error."""
    entity_id = "sensor.4_in_1_sensor_signal_strength"

    entity_registry.async_update_entity(entity_id, disabled_by=None)

    # reload integration and check if entity is correctly there
    await hass.config_entries.async_reload(integration.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "unknown"

    # Fire statistics updated event for node
    event = Event(
        "statistics updated",
        {
            "source": "node",
            "event": "statistics updated",
            "nodeId": zp3111.node_id,
            "statistics": {
                "commandsTX": 1,
                "commandsRX": 2,
                "commandsDroppedTX": 3,
                "commandsDroppedRX": 4,
                "timeoutResponse": 5,
                "rtt": 6,
                "rssi": 7,  # baseline
                "lwr": {
                    "protocolDataRate": 1,
                    "rssi": 1,
                    "repeaters": [],
                    "repeaterRSSI": [],
                    "routeFailedBetween": [],
                },
                "nlwr": {
                    "protocolDataRate": 2,
                    "rssi": 2,
                    "repeaters": [],
                    "repeaterRSSI": [],
                    "routeFailedBetween": [],
                },
                "lastSeen": "2024-01-01T00:00:00+0000",
            },
        },
    )
    zp3111.receive_event(event)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "7"

    event = Event(
        "statistics updated",
        {
            "source": "node",
            "event": "statistics updated",
            "nodeId": zp3111.node_id,
            "statistics": {
                "commandsTX": 1,
                "commandsRX": 2,
                "commandsDroppedTX": 3,
                "commandsDroppedRX": 4,
                "timeoutResponse": 5,
                "rtt": 6,
                "rssi": 125,  # no signal detected
                "lwr": {
                    "protocolDataRate": 1,
                    "rssi": 1,
                    "repeaters": [],
                    "repeaterRSSI": [],
                    "routeFailedBetween": [],
                },
                "nlwr": {
                    "protocolDataRate": 2,
                    "rssi": 2,
                    "repeaters": [],
                    "repeaterRSSI": [],
                    "routeFailedBetween": [],
                },
                "lastSeen": "2024-01-01T00:00:00+0000",
            },
        },
    )
    zp3111.receive_event(event)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "unknown"

    event = Event(
        "statistics updated",
        {
            "source": "node",
            "event": "statistics updated",
            "nodeId": zp3111.node_id,
            "statistics": {
                "commandsTX": 1,
                "commandsRX": 2,
                "commandsDroppedTX": 3,
                "commandsDroppedRX": 4,
                "timeoutResponse": 5,
                "rtt": 6,
                "rssi": 127,  # not available
                "lwr": {
                    "protocolDataRate": 1,
                    "rssi": 1,
                    "repeaters": [],
                    "repeaterRSSI": [],
                    "routeFailedBetween": [],
                },
                "nlwr": {
                    "protocolDataRate": 2,
                    "rssi": 2,
                    "repeaters": [],
                    "repeaterRSSI": [],
                    "routeFailedBetween": [],
                },
                "lastSeen": "2024-01-01T00:00:00+0000",
            },
        },
    )
    zp3111.receive_event(event)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "unavailable"

    event = Event(
        "statistics updated",
        {
            "source": "node",
            "event": "statistics updated",
            "nodeId": zp3111.node_id,
            "statistics": {
                "commandsTX": 1,
                "commandsRX": 2,
                "commandsDroppedTX": 3,
                "commandsDroppedRX": 4,
                "timeoutResponse": 5,
                "rtt": 6,
                "rssi": 126,  # receiver saturated
                "lwr": {
                    "protocolDataRate": 1,
                    "rssi": 1,
                    "repeaters": [],
                    "repeaterRSSI": [],
                    "routeFailedBetween": [],
                },
                "nlwr": {
                    "protocolDataRate": 2,
                    "rssi": 2,
                    "repeaters": [],
                    "repeaterRSSI": [],
                    "routeFailedBetween": [],
                },
                "lastSeen": "2024-01-01T00:00:00+0000",
            },
        },
    )
    zp3111.receive_event(event)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "unknown"


ENERGY_PRODUCTION_ENTITY_MAP = {
    "energy_production_power": {
        "state": 1.23,
        "attributes": {
            "unit_of_measurement": UnitOfPower.WATT,
            "device_class": SensorDeviceClass.POWER,
            "state_class": SensorStateClass.MEASUREMENT,
        },
    },
    "energy_production_total": {
        "state": 1234.56,
        "attributes": {
            "unit_of_measurement": UnitOfEnergy.WATT_HOUR,
            "device_class": SensorDeviceClass.ENERGY,
            "state_class": SensorStateClass.TOTAL_INCREASING,
        },
    },
    "energy_production_today": {
        "state": 123.45,
        "attributes": {
            "unit_of_measurement": UnitOfEnergy.WATT_HOUR,
            "device_class": SensorDeviceClass.ENERGY,
            "state_class": SensorStateClass.TOTAL_INCREASING,
        },
    },
    "energy_production_time": {
        "state": 123456.0,
        "attributes": {
            "unit_of_measurement": UnitOfTime.SECONDS,
            "device_class": SensorDeviceClass.DURATION,
        },
        "missing_attributes": ["state_class"],
    },
}


async def test_energy_production_sensors(
    hass: HomeAssistant, energy_production, client, integration
) -> None:
    """Test sensors for Energy Production CC."""
    for entity_id_suffix, state_data in ENERGY_PRODUCTION_ENTITY_MAP.items():
        state = hass.states.get(f"sensor.node_2_{entity_id_suffix}")
        assert state
        assert state.state == str(state_data["state"])
        for attr, val in state_data["attributes"].items():
            assert state.attributes[attr] == val

        for attr in state_data.get("missing_attributes", []):
            assert attr not in state.attributes
