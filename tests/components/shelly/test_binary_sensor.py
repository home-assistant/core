"""Tests for Shelly binary sensor platform."""
from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.shelly.const import SLEEP_PERIOD_MULTIPLIER
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.entity_registry import async_get

from . import (
    init_integration,
    mock_rest_update,
    mutate_rpc_device_status,
    register_device,
    register_entity,
)

from tests.common import mock_restore_cache

RELAY_BLOCK_ID = 0
SENSOR_BLOCK_ID = 3


async def test_block_binary_sensor(
    hass: HomeAssistant, mock_block_device, monkeypatch
) -> None:
    """Test block binary sensor."""
    entity_id = f"{BINARY_SENSOR_DOMAIN}.test_name_channel_1_overpowering"
    await init_integration(hass, 1)

    assert hass.states.get(entity_id).state == STATE_OFF

    monkeypatch.setattr(mock_block_device.blocks[RELAY_BLOCK_ID], "overpower", 1)
    mock_block_device.mock_update()

    assert hass.states.get(entity_id).state == STATE_ON


async def test_block_binary_sensor_extra_state_attr(
    hass: HomeAssistant, mock_block_device, monkeypatch
) -> None:
    """Test block binary sensor extra state attributes."""
    entity_id = f"{BINARY_SENSOR_DOMAIN}.test_name_gas"
    await init_integration(hass, 1)

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    assert state.attributes.get("detected") == "mild"

    monkeypatch.setattr(mock_block_device.blocks[SENSOR_BLOCK_ID], "gas", "none")
    mock_block_device.mock_update()

    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF
    assert state.attributes.get("detected") == "none"


async def test_block_rest_binary_sensor(
    hass: HomeAssistant, mock_block_device, monkeypatch
) -> None:
    """Test block REST binary sensor."""
    entity_id = register_entity(hass, BINARY_SENSOR_DOMAIN, "test_name_cloud", "cloud")
    monkeypatch.setitem(mock_block_device.status, "cloud", {"connected": False})
    await init_integration(hass, 1)

    assert hass.states.get(entity_id).state == STATE_OFF

    monkeypatch.setitem(mock_block_device.status["cloud"], "connected", True)
    await mock_rest_update(hass)

    assert hass.states.get(entity_id).state == STATE_ON


async def test_block_rest_binary_sensor_connected_battery_devices(
    hass: HomeAssistant, mock_block_device, monkeypatch
) -> None:
    """Test block REST binary sensor for connected battery devices."""
    entity_id = register_entity(hass, BINARY_SENSOR_DOMAIN, "test_name_cloud", "cloud")
    monkeypatch.setitem(mock_block_device.status, "cloud", {"connected": False})
    monkeypatch.setitem(mock_block_device.settings["device"], "type", "SHMOS-01")
    monkeypatch.setitem(mock_block_device.settings["coiot"], "update_period", 3600)
    await init_integration(hass, 1, model="SHMOS-01")

    assert hass.states.get(entity_id).state == STATE_OFF

    monkeypatch.setitem(mock_block_device.status["cloud"], "connected", True)

    # Verify no update on fast intervals
    await mock_rest_update(hass)
    assert hass.states.get(entity_id).state == STATE_OFF

    # Verify update on slow intervals
    await mock_rest_update(hass, seconds=SLEEP_PERIOD_MULTIPLIER * 3600)
    assert hass.states.get(entity_id).state == STATE_ON


async def test_block_sleeping_binary_sensor(
    hass: HomeAssistant, mock_block_device, monkeypatch
) -> None:
    """Test block sleeping binary sensor."""
    entity_id = f"{BINARY_SENSOR_DOMAIN}.test_name_motion"
    await init_integration(hass, 1, sleep_period=1000)

    # Sensor should be created when device is online
    assert hass.states.get(entity_id) is None

    # Make device online
    mock_block_device.mock_update()
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_OFF

    monkeypatch.setattr(mock_block_device.blocks[SENSOR_BLOCK_ID], "motion", 1)
    mock_block_device.mock_update()

    assert hass.states.get(entity_id).state == STATE_ON


async def test_block_restored_sleeping_binary_sensor(
    hass: HomeAssistant, mock_block_device, device_reg, monkeypatch
) -> None:
    """Test block restored sleeping binary sensor."""
    entry = await init_integration(hass, 1, sleep_period=1000, skip_setup=True)
    register_device(device_reg, entry)
    entity_id = register_entity(
        hass, BINARY_SENSOR_DOMAIN, "test_name_motion", "sensor_0-motion", entry
    )
    mock_restore_cache(hass, [State(entity_id, STATE_ON)])
    monkeypatch.setattr(mock_block_device, "initialized", False)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_ON

    # Make device online
    monkeypatch.setattr(mock_block_device, "initialized", True)
    mock_block_device.mock_update()
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_OFF


async def test_block_restored_sleeping_binary_sensor_no_last_state(
    hass: HomeAssistant, mock_block_device, device_reg, monkeypatch
) -> None:
    """Test block restored sleeping binary sensor missing last state."""
    entry = await init_integration(hass, 1, sleep_period=1000, skip_setup=True)
    register_device(device_reg, entry)
    entity_id = register_entity(
        hass, BINARY_SENSOR_DOMAIN, "test_name_motion", "sensor_0-motion", entry
    )
    monkeypatch.setattr(mock_block_device, "initialized", False)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_UNKNOWN

    # Make device online
    monkeypatch.setattr(mock_block_device, "initialized", True)
    mock_block_device.mock_update()
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_OFF


async def test_rpc_binary_sensor(
    hass: HomeAssistant, mock_rpc_device, monkeypatch
) -> None:
    """Test RPC binary sensor."""
    entity_id = f"{BINARY_SENSOR_DOMAIN}.test_cover_0_overpowering"
    await init_integration(hass, 2)

    assert hass.states.get(entity_id).state == STATE_OFF

    mutate_rpc_device_status(
        monkeypatch, mock_rpc_device, "cover:0", "errors", "overpower"
    )
    mock_rpc_device.mock_update()

    assert hass.states.get(entity_id).state == STATE_ON


async def test_rpc_binary_sensor_removal(
    hass: HomeAssistant, mock_rpc_device, monkeypatch
) -> None:
    """Test RPC binary sensor is removed due to removal_condition."""
    entity_registry = async_get(hass)
    entity_id = register_entity(
        hass, BINARY_SENSOR_DOMAIN, "test_cover_0_input", "input:0-input"
    )

    assert entity_registry.async_get(entity_id) is not None

    monkeypatch.setattr(mock_rpc_device, "status", {"input:0": {"state": False}})
    await init_integration(hass, 2)

    assert entity_registry.async_get(entity_id) is None


async def test_rpc_sleeping_binary_sensor(
    hass: HomeAssistant, mock_rpc_device, device_reg, monkeypatch
) -> None:
    """Test RPC online sleeping binary sensor."""
    entity_id = f"{BINARY_SENSOR_DOMAIN}.test_name_cloud"
    entry = await init_integration(hass, 2, sleep_period=1000)

    # Sensor should be created when device is online
    assert hass.states.get(entity_id) is None

    register_entity(hass, BINARY_SENSOR_DOMAIN, "test_name_cloud", "cloud-cloud", entry)

    # Make device online
    mock_rpc_device.mock_update()
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_OFF

    mutate_rpc_device_status(monkeypatch, mock_rpc_device, "cloud", "connected", True)
    mock_rpc_device.mock_update()

    assert hass.states.get(entity_id).state == STATE_ON

    # test external power sensor
    state = hass.states.get("binary_sensor.test_name_external_power")
    assert state
    assert state.state == STATE_ON


async def test_rpc_restored_sleeping_binary_sensor(
    hass: HomeAssistant, mock_rpc_device, device_reg, monkeypatch
) -> None:
    """Test RPC restored binary sensor."""
    entry = await init_integration(hass, 2, sleep_period=1000, skip_setup=True)
    register_device(device_reg, entry)
    entity_id = register_entity(
        hass, BINARY_SENSOR_DOMAIN, "test_name_cloud", "cloud-cloud", entry
    )

    mock_restore_cache(hass, [State(entity_id, STATE_ON)])
    monkeypatch.setattr(mock_rpc_device, "initialized", False)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_ON

    # Make device online
    monkeypatch.setattr(mock_rpc_device, "initialized", True)
    mock_rpc_device.mock_update()
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_OFF


async def test_rpc_restored_sleeping_binary_sensor_no_last_state(
    hass: HomeAssistant, mock_rpc_device, device_reg, monkeypatch
) -> None:
    """Test RPC restored sleeping binary sensor missing last state."""
    entry = await init_integration(hass, 2, sleep_period=1000, skip_setup=True)
    register_device(device_reg, entry)
    entity_id = register_entity(
        hass, BINARY_SENSOR_DOMAIN, "test_name_cloud", "cloud-cloud", entry
    )

    monkeypatch.setattr(mock_rpc_device, "initialized", False)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_UNKNOWN

    # Make device online
    monkeypatch.setattr(mock_rpc_device, "initialized", True)
    mock_rpc_device.mock_update()
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_OFF
