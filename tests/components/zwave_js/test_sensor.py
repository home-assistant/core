"""Test the Z-Wave JS sensor platform."""
import copy

import pytest
from zwave_js_server.const.command_class.meter import MeterType
from zwave_js_server.event import Event
from zwave_js_server.exceptions import FailedZWaveCommand
from zwave_js_server.model.node import Node

from homeassistant.components.sensor import (
    ATTR_OPTIONS,
    ATTR_STATE_CLASS,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.components.zwave_js.const import (
    ATTR_METER_TYPE,
    ATTR_METER_TYPE_NAME,
    ATTR_VALUE,
    DOMAIN,
    SERVICE_REFRESH_VALUE,
    SERVICE_RESET_METER,
)
from homeassistant.components.zwave_js.helpers import get_valueless_base_unique_id
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    ATTR_UNIT_OF_MEASUREMENT,
    PERCENTAGE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UV_INDEX,
    EntityCategory,
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

from .common import (
    AIR_TEMPERATURE_SENSOR,
    BATTERY_SENSOR,
    CURRENT_SENSOR,
    ENERGY_SENSOR,
    HUMIDITY_SENSOR,
    METER_ENERGY_SENSOR,
    NOTIFICATION_MOTION_SENSOR,
    POWER_SENSOR,
    VOLTAGE_SENSOR,
)


async def test_numeric_sensor(
    hass: HomeAssistant, multisensor_6, express_controls_ezmultipli, integration
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

    ent_reg = er.async_get(hass)
    entity_entry = ent_reg.async_get(BATTERY_SENSOR)
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

    state = hass.states.get("sensor.hsm200_illuminance")

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
    state = hass.states.get("sensor.hsm200_illuminance")
    assert state
    assert state.state == "0"


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
            "result": "",
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


async def test_disabled_notification_sensor(
    hass: HomeAssistant, multisensor_6, integration
) -> None:
    """Test sensor is created from Notification CC and is disabled."""
    ent_reg = er.async_get(hass)
    entity_entry = ent_reg.async_get(NOTIFICATION_MOTION_SENSOR)

    assert entity_entry
    assert entity_entry.disabled
    assert entity_entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION

    # Test enabling entity
    updated_entry = ent_reg.async_update_entity(
        entity_entry.entity_id, **{"disabled_by": None}
    )
    assert updated_entry != entity_entry
    assert updated_entry.disabled is False

    # reload integration and check if entity is correctly there
    await hass.config_entries.async_reload(integration.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(NOTIFICATION_MOTION_SENSOR)
    assert state.state == "Motion detection"
    assert state.attributes[ATTR_VALUE] == 8
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.ENUM
    assert state.attributes[ATTR_OPTIONS] == ["idle", "Motion detection"]

    event = Event(
        "value updated",
        {
            "source": "node",
            "event": "value updated",
            "nodeId": multisensor_6.node_id,
            "args": {
                "commandClassName": "Notification",
                "commandClass": 113,
                "endpoint": 0,
                "property": "Home Security",
                "propertyKey": "Motion sensor status",
                "newValue": None,
                "prevValue": 0,
                "propertyName": "Home Security",
                "propertyKeyName": "Motion sensor status",
            },
        },
    )

    multisensor_6.receive_event(event)
    await hass.async_block_till_done()
    state = hass.states.get(NOTIFICATION_MOTION_SENSOR)
    assert state
    assert state.state == STATE_UNKNOWN


async def test_config_parameter_sensor(
    hass: HomeAssistant, climate_adc_t3000, lock_id_lock_as_id150, integration
) -> None:
    """Test config parameter sensor is created."""
    sensor_entity_id = "sensor.adc_t3000_system_configuration_cool_stages"
    sensor_with_states_entity_id = "sensor.adc_t3000_power_source"
    ent_reg = er.async_get(hass)
    for entity_id in (sensor_entity_id, sensor_with_states_entity_id):
        entity_entry = ent_reg.async_get(entity_id)
        assert entity_entry
        assert entity_entry.disabled
        assert entity_entry.entity_category == EntityCategory.DIAGNOSTIC

    for entity_id in (sensor_entity_id, sensor_with_states_entity_id):
        updated_entry = ent_reg.async_update_entity(entity_id, **{"disabled_by": None})
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

    updated_entry = ent_reg.async_update_entity(
        entity_entry.entity_id, **{"disabled_by": None}
    )
    assert updated_entry != entity_entry
    assert updated_entry.disabled is False

    # reload integration and check if entity is correctly there
    await hass.config_entries.async_reload(integration.entry_id)
    await hass.async_block_till_done()


async def test_controller_status_sensor(
    hass: HomeAssistant, client, integration
) -> None:
    """Test controller status sensor is created and gets updated on controller state changes."""
    entity_id = "sensor.z_stick_gen5_usb_controller_status"
    ent_reg = er.async_get(hass)
    entity_entry = ent_reg.async_get(entity_id)

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
    hass: HomeAssistant, client, lock_id_lock_as_id150, integration
) -> None:
    """Test node status sensor is created and gets updated on node state changes."""
    node_status_entity_id = "sensor.z_wave_module_for_id_lock_150_and_101_node_status"
    node = lock_id_lock_as_id150
    ent_reg = er.async_get(hass)
    entity_entry = ent_reg.async_get(node_status_entity_id)

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
    node = driver.controller.nodes[1]
    assert node.is_controller_node
    assert (
        ent_reg.async_get_entity_id(
            DOMAIN,
            "sensor",
            f"{get_valueless_base_unique_id(driver, node)}.node_status",
        )
        is None
    )

    # Assert a controller status sensor entity is not created for a node
    assert (
        ent_reg.async_get_entity_id(
            DOMAIN,
            "sensor",
            f"{get_valueless_base_unique_id(driver, node)}.controller_status",
        )
        is None
    )


async def test_node_status_sensor_not_ready(
    hass: HomeAssistant,
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
    ent_reg = er.async_get(hass)
    entity_entry = ent_reg.async_get(node_status_entity_id)

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
        SERVICE_REFRESH_VALUE,
        {
            ATTR_ENTITY_ID: node_status_entity_id,
        },
        blocking=True,
    )
    await hass.async_block_till_done()
    assert "There is no value to refresh for this entity" in caplog.text


async def test_reset_meter(
    hass: HomeAssistant, client, aeon_smart_switch_6, integration
) -> None:
    """Test reset_meter service."""
    client.async_send_command.return_value = {}
    client.async_send_command_no_wait.return_value = {}

    # Test successful meter reset call
    await hass.services.async_call(
        DOMAIN,
        SERVICE_RESET_METER,
        {
            ATTR_ENTITY_ID: METER_ENERGY_SENSOR,
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
        SERVICE_RESET_METER,
        {
            ATTR_ENTITY_ID: METER_ENERGY_SENSOR,
            ATTR_METER_TYPE: 1,
            ATTR_VALUE: 2,
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

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RESET_METER,
            {ATTR_ENTITY_ID: METER_ENERGY_SENSOR},
            blocking=True,
        )


async def test_meter_attributes(
    hass: HomeAssistant, client, aeon_smart_switch_6, integration
) -> None:
    """Test meter entity attributes."""
    state = hass.states.get(METER_ENERGY_SENSOR)
    assert state
    assert state.attributes[ATTR_METER_TYPE] == MeterType.ELECTRIC.value
    assert state.attributes[ATTR_METER_TYPE_NAME] == MeterType.ELECTRIC.name
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.ENERGY
    assert state.attributes[ATTR_STATE_CLASS] is SensorStateClass.TOTAL_INCREASING


async def test_invalid_meter_scale(
    hass: HomeAssistant, client, aeon_smart_switch_6_state, integration
) -> None:
    """Test a meter sensor with an invalid scale."""
    node_state = copy.deepcopy(aeon_smart_switch_6_state)
    value = next(
        value
        for value in node_state["values"]
        if value["commandClass"] == 50
        and value["property"] == "value"
        and value["propertyKey"] == 65537
    )
    value["metadata"]["ccSpecific"]["scale"] = -1
    value["metadata"]["unit"] = None

    event = Event(
        "node added",
        {
            "source": "controller",
            "event": "node added",
            "node": node_state,
            "result": "",
        },
    )
    client.driver.controller.receive_event(event)
    await hass.async_block_till_done()

    state = hass.states.get(METER_ENERGY_SENSOR)
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
    # Add an ElectricScale.KILOVOLT_AMPERE_REACTIVE value to the state so we can test that
    # it is handled differently (no device class)
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
    "current_background_rssi_channel_0": -1,
    "average_background_rssi_channel_0": -2,
    "current_background_rssi_channel_1": -3,
    "average_background_rssi_channel_1": -4,
    "current_background_rssi_channel_2": STATE_UNKNOWN,
    "average_background_rssi_channel_2": STATE_UNKNOWN,
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
    "rssi": 7,
}


async def test_statistics_sensors_no_last_seen(
    hass: HomeAssistant, zp3111, client, integration, caplog: pytest.LogCaptureFixture
) -> None:
    """Test all statistics sensors but last seen which is enabled by default."""
    ent_reg = er.async_get(hass)

    for prefix, suffixes in (
        (CONTROLLER_STATISTICS_ENTITY_PREFIX, CONTROLLER_STATISTICS_SUFFIXES),
        (CONTROLLER_STATISTICS_ENTITY_PREFIX, CONTROLLER_STATISTICS_SUFFIXES_UNKNOWN),
        (NODE_STATISTICS_ENTITY_PREFIX, NODE_STATISTICS_SUFFIXES),
        (NODE_STATISTICS_ENTITY_PREFIX, NODE_STATISTICS_SUFFIXES_UNKNOWN),
    ):
        for suffix_key in suffixes:
            entry = ent_reg.async_get(f"{prefix}{suffix_key}")
            assert entry
            assert entry.disabled
            assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION

            ent_reg.async_update_entity(entry.entity_id, **{"disabled_by": None})

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
            entry = ent_reg.async_get(f"{prefix}{suffix_key}")
            assert entry
            assert not entry.disabled
            assert entry.disabled_by is None

            state = hass.states.get(entry.entity_id)
            assert state
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
                SERVICE_REFRESH_VALUE,
                {ATTR_ENTITY_ID: entity_id},
                blocking=True,
            )
    await hass.async_block_till_done()
    assert caplog.text.count("There is no value to refresh for this entity") == len(
        [
            *CONTROLLER_STATISTICS_SUFFIXES,
            *CONTROLLER_STATISTICS_SUFFIXES_UNKNOWN,
            *NODE_STATISTICS_SUFFIXES,
            *NODE_STATISTICS_SUFFIXES_UNKNOWN,
        ]
    )


async def test_last_seen_statistics_sensors(
    hass: HomeAssistant, zp3111, client, integration
) -> None:
    """Test last_seen statistics sensors."""
    ent_reg = er.async_get(hass)

    entity_id = f"{NODE_STATISTICS_ENTITY_PREFIX}last_seen"
    entry = ent_reg.async_get(entity_id)
    assert entry
    assert not entry.disabled

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "2024-01-01T12:00:00+00:00"


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
