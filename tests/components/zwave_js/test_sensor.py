"""Test the Z-Wave JS sensor platform."""
import copy

import pytest
from zwave_js_server.const.command_class.meter import MeterType
from zwave_js_server.event import Event
from zwave_js_server.model.node import Node

from homeassistant.components.sensor import (
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
    ATTR_ICON,
    ATTR_UNIT_OF_MEASUREMENT,
    PERCENTAGE,
    STATE_UNAVAILABLE,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import (
    AIR_TEMPERATURE_SENSOR,
    BATTERY_SENSOR,
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
    # TODO: Add UV_INDEX unit of measurement to this sensor
    assert ATTR_UNIT_OF_MEASUREMENT not in state.attributes
    assert ATTR_DEVICE_CLASS not in state.attributes
    # TODO: Add measurement state class to this sensor
    assert ATTR_STATE_CLASS not in state.attributes

    state = hass.states.get("sensor.hsm200_illuminance")

    assert state
    assert state.state == "61.0"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == PERCENTAGE
    assert ATTR_DEVICE_CLASS not in state.attributes
    assert state.attributes[ATTR_STATE_CLASS] == SensorStateClass.MEASUREMENT


async def test_energy_sensors(
    hass: HomeAssistant, hank_binary_switch, integration
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
    assert state.state == "0.16"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfEnergy.KILO_WATT_HOUR
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.ENERGY
    assert state.attributes[ATTR_STATE_CLASS] is SensorStateClass.TOTAL_INCREASING

    state = hass.states.get(VOLTAGE_SENSOR)

    assert state
    assert state.state == "122.96"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfElectricPotential.VOLT
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.VOLTAGE

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
    assert state.attributes["value"] == 8


async def test_disabled_indcator_sensor(
    hass: HomeAssistant, climate_radio_thermostat_ct100_plus, integration
) -> None:
    """Test sensor is created from Indicator CC and is disabled."""
    ent_reg = er.async_get(hass)
    entity_entry = ent_reg.async_get(INDICATOR_SENSOR)

    assert entity_entry
    assert entity_entry.disabled
    assert entity_entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION


async def test_config_parameter_sensor(
    hass: HomeAssistant, lock_id_lock_as_id150, integration
) -> None:
    """Test config parameter sensor is created."""
    ent_reg = er.async_get(hass)
    entity_entry = ent_reg.async_get(ID_LOCK_CONFIG_PARAMETER_SENSOR)
    assert entity_entry
    assert entity_entry.disabled


async def test_node_status_sensor(
    hass: HomeAssistant, client, lock_id_lock_as_id150, integration
) -> None:
    """Test node status sensor is created and gets updated on node state changes."""
    NODE_STATUS_ENTITY = "sensor.z_wave_module_for_id_lock_150_and_101_node_status"
    node = lock_id_lock_as_id150
    ent_reg = er.async_get(hass)
    entity_entry = ent_reg.async_get(NODE_STATUS_ENTITY)

    assert not entity_entry.disabled
    assert entity_entry.entity_category is EntityCategory.DIAGNOSTIC
    assert hass.states.get(NODE_STATUS_ENTITY).state == "alive"

    # Test transitions work
    event = Event(
        "dead", data={"source": "node", "event": "dead", "nodeId": node.node_id}
    )
    node.receive_event(event)
    assert hass.states.get(NODE_STATUS_ENTITY).state == "dead"
    assert hass.states.get(NODE_STATUS_ENTITY).attributes[ATTR_ICON] == "mdi:robot-dead"

    event = Event(
        "wake up", data={"source": "node", "event": "wake up", "nodeId": node.node_id}
    )
    node.receive_event(event)
    assert hass.states.get(NODE_STATUS_ENTITY).state == "awake"
    assert hass.states.get(NODE_STATUS_ENTITY).attributes[ATTR_ICON] == "mdi:eye"

    event = Event(
        "sleep", data={"source": "node", "event": "sleep", "nodeId": node.node_id}
    )
    node.receive_event(event)
    assert hass.states.get(NODE_STATUS_ENTITY).state == "asleep"
    assert hass.states.get(NODE_STATUS_ENTITY).attributes[ATTR_ICON] == "mdi:sleep"

    event = Event(
        "alive", data={"source": "node", "event": "alive", "nodeId": node.node_id}
    )
    node.receive_event(event)
    assert hass.states.get(NODE_STATUS_ENTITY).state == "alive"
    assert (
        hass.states.get(NODE_STATUS_ENTITY).attributes[ATTR_ICON] == "mdi:heart-pulse"
    )

    # Disconnect the client and make sure the entity is still available
    await client.disconnect()
    assert hass.states.get(NODE_STATUS_ENTITY).state != STATE_UNAVAILABLE

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


async def test_node_status_sensor_not_ready(
    hass: HomeAssistant,
    client,
    lock_id_lock_as_id150_not_ready,
    lock_id_lock_as_id150_state,
    integration,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test node status sensor is created and available if node is not ready."""
    NODE_STATUS_ENTITY = "sensor.z_wave_module_for_id_lock_150_and_101_node_status"
    node = lock_id_lock_as_id150_not_ready
    assert not node.ready
    ent_reg = er.async_get(hass)
    entity_entry = ent_reg.async_get(NODE_STATUS_ENTITY)

    assert not entity_entry.disabled
    assert hass.states.get(NODE_STATUS_ENTITY)
    assert hass.states.get(NODE_STATUS_ENTITY).state == "alive"

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
    assert hass.states.get(NODE_STATUS_ENTITY)
    assert hass.states.get(NODE_STATUS_ENTITY).state == "alive"

    await hass.services.async_call(
        DOMAIN,
        SERVICE_REFRESH_VALUE,
        {
            ATTR_ENTITY_ID: NODE_STATUS_ENTITY,
        },
        blocking=True,
    )

    assert "There is no value to refresh for this entity" in caplog.text


async def test_reset_meter(
    hass: HomeAssistant,
    client,
    aeon_smart_switch_6,
    integration,
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


async def test_meter_attributes(
    hass: HomeAssistant,
    client,
    aeon_smart_switch_6,
    integration,
) -> None:
    """Test meter entity attributes."""
    state = hass.states.get(METER_ENERGY_SENSOR)
    assert state
    assert state.attributes[ATTR_METER_TYPE] == MeterType.ELECTRIC.value
    assert state.attributes[ATTR_METER_TYPE_NAME] == MeterType.ELECTRIC.name
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.ENERGY
    assert state.attributes[ATTR_STATE_CLASS] is SensorStateClass.TOTAL_INCREASING


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
