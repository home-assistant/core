"""Test for the LCN binary sensor platform."""
from pypck.inputs import ModStatusBinSensors, ModStatusKeyLocks, ModStatusVar
from pypck.lcn_addr import LcnAddr
from pypck.lcn_defs import Var, VarValue

from homeassistant.components.lcn.helpers import get_device_connection
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.helpers import entity_registry as er

BINARY_SENSOR_LOCKREGULATOR1 = "binary_sensor.sensor_lockregulator1"
BINARY_SENSOR_SENSOR1 = "binary_sensor.binary_sensor1"
BINARY_SENSOR_KEYLOCK = "binary_sensor.sensor_keylock"


async def test_setup_lcn_binary_sensor(hass, lcn_connection):
    """Test the setup of binary sensor."""
    for entity_id in (
        BINARY_SENSOR_LOCKREGULATOR1,
        BINARY_SENSOR_SENSOR1,
        BINARY_SENSOR_KEYLOCK,
    ):
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == STATE_UNKNOWN


async def test_entity_state(hass, lcn_connection):
    """Test state of entity."""
    state = hass.states.get(BINARY_SENSOR_LOCKREGULATOR1)
    assert state

    state = hass.states.get(BINARY_SENSOR_SENSOR1)
    assert state

    state = hass.states.get(BINARY_SENSOR_KEYLOCK)
    assert state


async def test_entity_attributes(hass, entry, lcn_connection):
    """Test the attributes of an entity."""
    entity_registry = er.async_get(hass)

    entity_setpoint1 = entity_registry.async_get(BINARY_SENSOR_LOCKREGULATOR1)
    assert entity_setpoint1
    assert entity_setpoint1.unique_id == f"{entry.entry_id}-m000007-r1varsetpoint"
    assert entity_setpoint1.original_name == "Sensor_LockRegulator1"

    entity_binsensor1 = entity_registry.async_get(BINARY_SENSOR_SENSOR1)
    assert entity_binsensor1
    assert entity_binsensor1.unique_id == f"{entry.entry_id}-m000007-binsensor1"
    assert entity_binsensor1.original_name == "Binary_Sensor1"

    entity_keylock = entity_registry.async_get(BINARY_SENSOR_KEYLOCK)
    assert entity_keylock
    assert entity_keylock.unique_id == f"{entry.entry_id}-m000007-a5"
    assert entity_keylock.original_name == "Sensor_KeyLock"


async def test_pushed_lock_setpoint_status_change(hass, entry, lcn_connection):
    """Test the lock setpoint sensor changes its state on status received."""
    device_connection = get_device_connection(hass, (0, 7, False), entry)
    address = LcnAddr(0, 7, False)

    # push status lock setpoint
    inp = ModStatusVar(address, Var.R1VARSETPOINT, VarValue(0x8000))
    await device_connection.async_process_input(inp)
    await hass.async_block_till_done()

    state = hass.states.get(BINARY_SENSOR_LOCKREGULATOR1)
    assert state is not None
    assert state.state == STATE_ON

    # push status unlock setpoint
    inp = ModStatusVar(address, Var.R1VARSETPOINT, VarValue(0x7FFF))
    await device_connection.async_process_input(inp)
    await hass.async_block_till_done()

    state = hass.states.get(BINARY_SENSOR_LOCKREGULATOR1)
    assert state is not None
    assert state.state == STATE_OFF


async def test_pushed_binsensor_status_change(hass, entry, lcn_connection):
    """Test the binary port sensor changes its state on status received."""
    device_connection = get_device_connection(hass, (0, 7, False), entry)
    address = LcnAddr(0, 7, False)
    states = [False] * 8

    # push status binary port "off"
    inp = ModStatusBinSensors(address, states)
    await device_connection.async_process_input(inp)
    await hass.async_block_till_done()

    state = hass.states.get(BINARY_SENSOR_SENSOR1)
    assert state is not None
    assert state.state == STATE_OFF

    # push status binary port "on"
    states[0] = True
    inp = ModStatusBinSensors(address, states)
    await device_connection.async_process_input(inp)
    await hass.async_block_till_done()

    state = hass.states.get(BINARY_SENSOR_SENSOR1)
    assert state is not None
    assert state.state == STATE_ON


async def test_pushed_keylock_status_change(hass, entry, lcn_connection):
    """Test the keylock sensor changes its state on status received."""
    device_connection = get_device_connection(hass, (0, 7, False), entry)
    address = LcnAddr(0, 7, False)
    states = [[False] * 8 for i in range(4)]

    # push status keylock "off"
    inp = ModStatusKeyLocks(address, states)
    await device_connection.async_process_input(inp)
    await hass.async_block_till_done()

    state = hass.states.get(BINARY_SENSOR_KEYLOCK)
    assert state is not None
    assert state.state == STATE_OFF

    # push status keylock "on"
    states[0][4] = True
    inp = ModStatusKeyLocks(address, states)
    await device_connection.async_process_input(inp)
    await hass.async_block_till_done()

    state = hass.states.get(BINARY_SENSOR_KEYLOCK)
    assert state is not None
    assert state.state == STATE_ON


async def test_unload_config_entry(hass, entry, lcn_connection):
    """Test the binary sensor is removed when the config entry is unloaded."""
    await hass.config_entries.async_unload(entry.entry_id)
    assert hass.states.get(BINARY_SENSOR_LOCKREGULATOR1).state == STATE_UNAVAILABLE
    assert hass.states.get(BINARY_SENSOR_SENSOR1).state == STATE_UNAVAILABLE
    assert hass.states.get(BINARY_SENSOR_KEYLOCK).state == STATE_UNAVAILABLE
