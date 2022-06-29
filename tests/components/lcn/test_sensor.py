"""Test for the LCN sensor platform."""
from pypck.inputs import ModStatusLedsAndLogicOps, ModStatusVar
from pypck.lcn_addr import LcnAddr
from pypck.lcn_defs import LedStatus, LogicOpStatus, Var, VarValue

from homeassistant.components.lcn.helpers import get_device_connection
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    TEMP_CELSIUS,
)
from homeassistant.helpers import entity_registry as er

SENSOR_VAR1 = "sensor.sensor_var1"
SENSOR_SETPOINT1 = "sensor.sensor_setpoint1"
SENSOR_LED6 = "sensor.sensor_led6"
SENSOR_LOGICOP1 = "sensor.sensor_logicop1"


async def test_setup_lcn_sensor(hass, entry, lcn_connection):
    """Test the setup of sensor."""
    for entity_id in (
        SENSOR_VAR1,
        SENSOR_SETPOINT1,
        SENSOR_LED6,
        SENSOR_LOGICOP1,
    ):
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == STATE_UNKNOWN


async def test_entity_state(hass, lcn_connection):
    """Test state of entity."""
    state = hass.states.get(SENSOR_VAR1)
    assert state
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == TEMP_CELSIUS

    state = hass.states.get(SENSOR_SETPOINT1)
    assert state
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == TEMP_CELSIUS

    state = hass.states.get(SENSOR_LED6)
    assert state

    state = hass.states.get(SENSOR_LOGICOP1)
    assert state


async def test_entity_attributes(hass, entry, lcn_connection):
    """Test the attributes of an entity."""
    entity_registry = er.async_get(hass)

    entity_var1 = entity_registry.async_get(SENSOR_VAR1)
    assert entity_var1
    assert entity_var1.unique_id == f"{entry.entry_id}-m000007-var1"
    assert entity_var1.original_name == "Sensor_Var1"

    entity_r1varsetpoint = entity_registry.async_get(SENSOR_SETPOINT1)
    assert entity_r1varsetpoint
    assert entity_r1varsetpoint.unique_id == f"{entry.entry_id}-m000007-r1varsetpoint"
    assert entity_r1varsetpoint.original_name == "Sensor_Setpoint1"

    entity_led6 = entity_registry.async_get(SENSOR_LED6)
    assert entity_led6
    assert entity_led6.unique_id == f"{entry.entry_id}-m000007-led6"
    assert entity_led6.original_name == "Sensor_Led6"

    entity_logicop1 = entity_registry.async_get(SENSOR_LOGICOP1)
    assert entity_logicop1
    assert entity_logicop1.unique_id == f"{entry.entry_id}-m000007-logicop1"
    assert entity_logicop1.original_name == "Sensor_LogicOp1"


async def test_pushed_variable_status_change(hass, entry, lcn_connection):
    """Test the variable sensor changes its state on status received."""
    device_connection = get_device_connection(hass, (0, 7, False), entry)
    address = LcnAddr(0, 7, False)

    # push status variable
    inp = ModStatusVar(address, Var.VAR1, VarValue.from_celsius(42))
    await device_connection.async_process_input(inp)
    await hass.async_block_till_done()

    state = hass.states.get(SENSOR_VAR1)
    assert state is not None
    assert float(state.state) == 42.0

    # push status setpoint
    inp = ModStatusVar(address, Var.R1VARSETPOINT, VarValue.from_celsius(42))
    await device_connection.async_process_input(inp)
    await hass.async_block_till_done()

    state = hass.states.get(SENSOR_SETPOINT1)
    assert state is not None
    assert float(state.state) == 42.0


async def test_pushed_ledlogicop_status_change(hass, entry, lcn_connection):
    """Test the led and logicop sensor changes its state on status received."""
    device_connection = get_device_connection(hass, (0, 7, False), entry)
    address = LcnAddr(0, 7, False)

    states_led = [LedStatus.OFF] * 12
    states_logicop = [LogicOpStatus.NONE] * 4

    states_led[5] = LedStatus.ON
    states_logicop[0] = LogicOpStatus.ALL

    # push status led and logicop
    inp = ModStatusLedsAndLogicOps(address, states_led, states_logicop)
    await device_connection.async_process_input(inp)
    await hass.async_block_till_done()

    state = hass.states.get(SENSOR_LED6)
    assert state is not None
    assert state.state == "on"

    state = hass.states.get(SENSOR_LOGICOP1)
    assert state is not None
    assert state.state == "all"


async def test_unload_config_entry(hass, entry, lcn_connection):
    """Test the sensor is removed when the config entry is unloaded."""
    await hass.config_entries.async_unload(entry.entry_id)
    assert hass.states.get(SENSOR_VAR1).state == STATE_UNAVAILABLE
    assert hass.states.get(SENSOR_SETPOINT1).state == STATE_UNAVAILABLE
    assert hass.states.get(SENSOR_LED6).state == STATE_UNAVAILABLE
    assert hass.states.get(SENSOR_LOGICOP1).state == STATE_UNAVAILABLE
