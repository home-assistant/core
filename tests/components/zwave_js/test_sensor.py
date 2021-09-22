"""Test the Z-Wave JS sensor platform."""
import copy

from zwave_js_server.const.command_class.meter import MeterType
from zwave_js_server.event import Event
from zwave_js_server.model.node import Node

from homeassistant.components.sensor import (
    ATTR_STATE_CLASS,
    STATE_CLASS_MEASUREMENT,
    STATE_CLASS_TOTAL_INCREASING,
)
from homeassistant.components.zwave_js.const import (
    ATTR_METER_TYPE,
    ATTR_METER_TYPE_NAME,
    ATTR_VALUE,
    DOMAIN,
    SERVICE_RESET_METER,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    DEVICE_CLASS_CURRENT,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_VOLTAGE,
    ELECTRIC_CURRENT_AMPERE,
    ELECTRIC_POTENTIAL_VOLT,
    ENERGY_KILO_WATT_HOUR,
    POWER_WATT,
    STATE_UNAVAILABLE,
    TEMP_CELSIUS,
)
from homeassistant.helpers import entity_registry as er

from .common import (
    AIR_TEMPERATURE_SENSOR,
    CURRENT_SENSOR,
    ENERGY_SENSOR,
    HUMIDITY_SENSOR,
    ID_LOCK_CONFIG_PARAMETER_SENSOR,
    INDICATOR_SENSOR,
    METER_ENERGY_SENSOR,
    NOTIFICATION_MOTION_SENSOR,
    POWER_SENSOR,
    VOLTAGE_SENSOR,
)


async def test_numeric_sensor(hass, multisensor_6, integration):
    """Test the numeric sensor."""
    state = hass.states.get(AIR_TEMPERATURE_SENSOR)

    assert state
    assert state.state == "9.0"
    assert state.attributes["unit_of_measurement"] == TEMP_CELSIUS
    assert state.attributes["device_class"] == DEVICE_CLASS_TEMPERATURE

    state = hass.states.get(HUMIDITY_SENSOR)

    assert state
    assert state.state == "65.0"
    assert state.attributes["unit_of_measurement"] == "%"
    assert state.attributes["device_class"] == DEVICE_CLASS_HUMIDITY


async def test_energy_sensors(hass, hank_binary_switch, integration):
    """Test power and energy sensors."""
    state = hass.states.get(POWER_SENSOR)

    assert state
    assert state.state == "0.0"
    assert state.attributes["unit_of_measurement"] == POWER_WATT
    assert state.attributes["device_class"] == DEVICE_CLASS_POWER
    assert state.attributes["state_class"] == STATE_CLASS_MEASUREMENT

    state = hass.states.get(ENERGY_SENSOR)

    assert state
    assert state.state == "0.16"
    assert state.attributes["unit_of_measurement"] == ENERGY_KILO_WATT_HOUR
    assert state.attributes["device_class"] == DEVICE_CLASS_ENERGY
    assert state.attributes["state_class"] == STATE_CLASS_TOTAL_INCREASING

    state = hass.states.get(VOLTAGE_SENSOR)

    assert state
    assert state.state == "122.96"
    assert state.attributes["unit_of_measurement"] == ELECTRIC_POTENTIAL_VOLT
    assert state.attributes["device_class"] == DEVICE_CLASS_VOLTAGE

    state = hass.states.get(CURRENT_SENSOR)

    assert state
    assert state.state == "0.0"
    assert state.attributes["unit_of_measurement"] == ELECTRIC_CURRENT_AMPERE
    assert state.attributes["device_class"] == DEVICE_CLASS_CURRENT


async def test_disabled_notification_sensor(hass, multisensor_6, integration):
    """Test sensor is created from Notification CC and is disabled."""
    ent_reg = er.async_get(hass)
    entity_entry = ent_reg.async_get(NOTIFICATION_MOTION_SENSOR)

    assert entity_entry
    assert entity_entry.disabled
    assert entity_entry.disabled_by == er.DISABLED_INTEGRATION

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
    assert state.attributes["value"] == 8


async def test_disabled_indcator_sensor(
    hass, climate_radio_thermostat_ct100_plus, integration
):
    """Test sensor is created from Indicator CC and is disabled."""
    ent_reg = er.async_get(hass)
    entity_entry = ent_reg.async_get(INDICATOR_SENSOR)

    assert entity_entry
    assert entity_entry.disabled
    assert entity_entry.disabled_by == er.DISABLED_INTEGRATION


async def test_config_parameter_sensor(hass, lock_id_lock_as_id150, integration):
    """Test config parameter sensor is created."""
    ent_reg = er.async_get(hass)
    entity_entry = ent_reg.async_get(ID_LOCK_CONFIG_PARAMETER_SENSOR)
    assert entity_entry
    assert entity_entry.disabled


async def test_node_status_sensor(hass, client, lock_id_lock_as_id150, integration):
    """Test node status sensor is created and gets updated on node state changes."""
    NODE_STATUS_ENTITY = "sensor.z_wave_module_for_id_lock_150_and_101_node_status"
    node = lock_id_lock_as_id150
    ent_reg = er.async_get(hass)
    entity_entry = ent_reg.async_get(NODE_STATUS_ENTITY)
    assert entity_entry.disabled
    assert entity_entry.disabled_by == er.DISABLED_INTEGRATION
    updated_entry = ent_reg.async_update_entity(
        entity_entry.entity_id, **{"disabled_by": None}
    )

    await hass.config_entries.async_reload(integration.entry_id)
    await hass.async_block_till_done()

    assert not updated_entry.disabled
    assert hass.states.get(NODE_STATUS_ENTITY).state == "alive"

    # Test transitions work
    event = Event(
        "dead", data={"source": "node", "event": "dead", "nodeId": node.node_id}
    )
    node.receive_event(event)
    assert hass.states.get(NODE_STATUS_ENTITY).state == "dead"

    event = Event(
        "wake up", data={"source": "node", "event": "wake up", "nodeId": node.node_id}
    )
    node.receive_event(event)
    assert hass.states.get(NODE_STATUS_ENTITY).state == "awake"

    event = Event(
        "sleep", data={"source": "node", "event": "sleep", "nodeId": node.node_id}
    )
    node.receive_event(event)
    assert hass.states.get(NODE_STATUS_ENTITY).state == "asleep"

    event = Event(
        "alive", data={"source": "node", "event": "alive", "nodeId": node.node_id}
    )
    node.receive_event(event)
    assert hass.states.get(NODE_STATUS_ENTITY).state == "alive"

    # Disconnect the client and make sure the entity is still available
    await client.disconnect()
    assert hass.states.get(NODE_STATUS_ENTITY).state != STATE_UNAVAILABLE


async def test_node_status_sensor_not_ready(
    hass,
    client,
    lock_id_lock_as_id150_not_ready,
    lock_id_lock_as_id150_state,
    integration,
):
    """Test node status sensor is created and available if node is not ready."""
    NODE_STATUS_ENTITY = "sensor.z_wave_module_for_id_lock_150_and_101_node_status"
    node = lock_id_lock_as_id150_not_ready
    assert not node.ready
    ent_reg = er.async_get(hass)
    entity_entry = ent_reg.async_get(NODE_STATUS_ENTITY)
    assert entity_entry.disabled
    assert entity_entry.disabled_by == er.DISABLED_INTEGRATION
    updated_entry = ent_reg.async_update_entity(
        entity_entry.entity_id, **{"disabled_by": None}
    )

    await hass.config_entries.async_reload(integration.entry_id)
    await hass.async_block_till_done()

    assert not updated_entry.disabled
    assert hass.states.get(NODE_STATUS_ENTITY)
    assert hass.states.get(NODE_STATUS_ENTITY).state == "alive"

    # Mark node as ready
    event = Event("ready", {"nodeState": lock_id_lock_as_id150_state})
    node.receive_event(event)
    assert node.ready
    assert hass.states.get(NODE_STATUS_ENTITY)
    assert hass.states.get(NODE_STATUS_ENTITY).state == "alive"


async def test_reset_meter(
    hass,
    client,
    aeon_smart_switch_6,
    integration,
):
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


async def test_meter_attributes(
    hass,
    client,
    aeon_smart_switch_6,
    integration,
):
    """Test meter entity attributes."""
    state = hass.states.get(METER_ENERGY_SENSOR)
    assert state
    assert state.attributes[ATTR_METER_TYPE] == MeterType.ELECTRIC.value
    assert state.attributes[ATTR_METER_TYPE_NAME] == MeterType.ELECTRIC.name
    assert state.attributes[ATTR_DEVICE_CLASS] == DEVICE_CLASS_ENERGY
    assert state.attributes[ATTR_STATE_CLASS] == STATE_CLASS_TOTAL_INCREASING


async def test_special_meters(hass, aeon_smart_switch_6_state, client, integration):
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
    assert state.attributes[ATTR_STATE_CLASS] == STATE_CLASS_TOTAL_INCREASING

    state = hass.states.get("sensor.smart_switch_6_electric_consumed_kva_reactive_11")
    assert state
    assert ATTR_DEVICE_CLASS not in state.attributes
    assert state.attributes[ATTR_STATE_CLASS] == STATE_CLASS_MEASUREMENT
