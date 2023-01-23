"""Tests for Shelly sensor platform."""


from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import State
from homeassistant.helpers.entity_registry import async_get

from . import (
    init_integration,
    mock_polling_rpc_update,
    mock_rest_update,
    mutate_rpc_device_status,
    register_device,
    register_entity,
)

from tests.common import mock_restore_cache

RELAY_BLOCK_ID = 0
SENSOR_BLOCK_ID = 3
DEVICE_BLOCK_ID = 4


async def test_block_sensor(hass, mock_block_device, monkeypatch):
    """Test block sensor."""
    entity_id = f"{SENSOR_DOMAIN}.test_name_channel_1_power"
    await init_integration(hass, 1)

    assert hass.states.get(entity_id).state == "53.4"

    monkeypatch.setattr(mock_block_device.blocks[RELAY_BLOCK_ID], "power", 60.1)
    mock_block_device.mock_update()

    assert hass.states.get(entity_id).state == "60.1"


async def test_block_rest_sensor(hass, mock_block_device, monkeypatch):
    """Test block REST sensor."""
    entity_id = register_entity(hass, SENSOR_DOMAIN, "test_name_rssi", "rssi")
    await init_integration(hass, 1)

    assert hass.states.get(entity_id).state == "-64"

    monkeypatch.setitem(mock_block_device.status["wifi_sta"], "rssi", -71)
    await mock_rest_update(hass)

    assert hass.states.get(entity_id).state == "-71"


async def test_block_sleeping_sensor(hass, mock_block_device, monkeypatch):
    """Test block sleeping sensor."""
    monkeypatch.setattr(
        mock_block_device.blocks[DEVICE_BLOCK_ID], "sensor_ids", {"battery": 98}
    )
    entity_id = f"{SENSOR_DOMAIN}.test_name_temperature"
    await init_integration(hass, 1, sleep_period=1000)

    # Sensor should be created when device is online
    assert hass.states.get(entity_id) is None

    # Make device online
    mock_block_device.mock_update()
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "22.1"

    monkeypatch.setattr(mock_block_device.blocks[SENSOR_BLOCK_ID], "temp", 23.4)
    mock_block_device.mock_update()

    assert hass.states.get(entity_id).state == "23.4"


async def test_block_restored_sleeping_sensor(
    hass, mock_block_device, device_reg, monkeypatch
):
    """Test block restored sleeping sensor."""
    entry = await init_integration(hass, 1, sleep_period=1000, skip_setup=True)
    register_device(device_reg, entry)
    entity_id = register_entity(
        hass, SENSOR_DOMAIN, "test_name_temperature", "sensor_0-temp", entry
    )
    mock_restore_cache(hass, [State(entity_id, "20.4")])
    monkeypatch.setattr(mock_block_device, "initialized", False)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "20.4"

    # Make device online
    monkeypatch.setattr(mock_block_device, "initialized", True)
    mock_block_device.mock_update()
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "22.1"


async def test_block_sensor_error(hass, mock_block_device, monkeypatch):
    """Test block sensor unavailable on sensor error."""
    entity_id = f"{SENSOR_DOMAIN}.test_name_battery"
    await init_integration(hass, 1)

    assert hass.states.get(entity_id).state == "98"

    monkeypatch.setattr(mock_block_device.blocks[DEVICE_BLOCK_ID], "battery", -1)
    mock_block_device.mock_update()

    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE


async def test_block_sensor_removal(hass, mock_block_device, monkeypatch):
    """Test block sensor is removed due to removal_condition."""
    entity_registry = async_get(hass)
    entity_id = register_entity(
        hass, SENSOR_DOMAIN, "test_name_battery", "device_0-battery"
    )

    assert entity_registry.async_get(entity_id) is not None

    monkeypatch.setitem(mock_block_device.settings, "external_power", 1)
    await init_integration(hass, 1)

    assert entity_registry.async_get(entity_id) is None


async def test_block_not_matched_restored_sleeping_sensor(
    hass, mock_block_device, device_reg, monkeypatch
):
    """Test block not matched to restored sleeping sensor."""
    entry = await init_integration(hass, 1, sleep_period=1000, skip_setup=True)
    register_device(device_reg, entry)
    entity_id = register_entity(
        hass, SENSOR_DOMAIN, "test_name_temperature", "sensor_0-temp", entry
    )
    mock_restore_cache(hass, [State(entity_id, "20.4")])
    monkeypatch.setattr(mock_block_device, "initialized", False)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "20.4"

    # Make device online
    monkeypatch.setattr(mock_block_device.blocks[SENSOR_BLOCK_ID], "type", "other_type")
    monkeypatch.setattr(mock_block_device, "initialized", True)
    mock_block_device.mock_update()
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "20.4"


async def test_block_sensor_without_value(hass, mock_block_device, monkeypatch):
    """Test block sensor without value is not created."""
    entity_id = f"{SENSOR_DOMAIN}.test_name_battery"
    monkeypatch.setattr(mock_block_device.blocks[DEVICE_BLOCK_ID], "battery", None)
    await init_integration(hass, 1)

    assert hass.states.get(entity_id) is None


async def test_block_sensor_unknown_value(hass, mock_block_device, monkeypatch):
    """Test block sensor unknown value."""
    entity_id = f"{SENSOR_DOMAIN}.test_name_battery"
    await init_integration(hass, 1)

    monkeypatch.setattr(mock_block_device.blocks[DEVICE_BLOCK_ID], "battery", None)
    mock_block_device.mock_update()

    assert hass.states.get(entity_id).state == STATE_UNKNOWN


async def test_rpc_sensor(hass, mock_rpc_device, monkeypatch) -> None:
    """Test RPC sensor."""
    entity_id = f"{SENSOR_DOMAIN}.test_cover_0_power"
    await init_integration(hass, 2)

    assert hass.states.get(entity_id).state == "85.3"

    mutate_rpc_device_status(monkeypatch, mock_rpc_device, "cover:0", "apower", "88.2")
    mock_rpc_device.mock_update()

    assert hass.states.get(entity_id).state == "88.2"

    mutate_rpc_device_status(monkeypatch, mock_rpc_device, "cover:0", "apower", None)
    mock_rpc_device.mock_update()

    assert hass.states.get(entity_id).state == STATE_UNKNOWN


async def test_rpc_sensor_error(hass, mock_rpc_device, monkeypatch):
    """Test RPC sensor unavailable on sensor error."""
    entity_id = f"{SENSOR_DOMAIN}.test_name_voltmeter"
    await init_integration(hass, 2)

    assert hass.states.get(entity_id).state == "4.3"

    mutate_rpc_device_status(monkeypatch, mock_rpc_device, "voltmeter", "voltage", None)
    mock_rpc_device.mock_update()

    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE


async def test_rpc_polling_sensor(hass, mock_rpc_device, monkeypatch) -> None:
    """Test RPC polling sensor."""
    entity_id = register_entity(hass, SENSOR_DOMAIN, "test_name_rssi", "wifi-rssi")
    await init_integration(hass, 2)

    assert hass.states.get(entity_id).state == "-63"

    mutate_rpc_device_status(monkeypatch, mock_rpc_device, "wifi", "rssi", "-70")
    await mock_polling_rpc_update(hass)

    assert hass.states.get(entity_id).state == "-70"


async def test_rpc_sleeping_sensor(
    hass, mock_rpc_device, device_reg, monkeypatch
) -> None:
    """Test RPC online sleeping sensor."""
    entity_id = f"{SENSOR_DOMAIN}.test_name_temperature"
    entry = await init_integration(hass, 2, sleep_period=1000)

    # Sensor should be created when device is online
    assert hass.states.get(entity_id) is None

    register_entity(
        hass,
        SENSOR_DOMAIN,
        "test_name_temperature",
        "temperature:0-temperature_0",
        entry,
    )

    # Make device online
    mock_rpc_device.mock_update()
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "22.9"

    mutate_rpc_device_status(monkeypatch, mock_rpc_device, "temperature:0", "tC", 23.4)
    mock_rpc_device.mock_update()

    assert hass.states.get(entity_id).state == "23.4"


async def test_rpc_restored_sleeping_sensor(
    hass, mock_rpc_device, device_reg, monkeypatch
):
    """Test RPC restored sensor."""
    entry = await init_integration(hass, 2, sleep_period=1000, skip_setup=True)
    register_device(device_reg, entry)
    entity_id = register_entity(
        hass,
        SENSOR_DOMAIN,
        "test_name_temperature",
        "temperature:0-temperature_0",
        entry,
    )

    mock_restore_cache(hass, [State(entity_id, "21.0")])
    monkeypatch.setattr(mock_rpc_device, "initialized", False)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "21.0"

    # Make device online
    monkeypatch.setattr(mock_rpc_device, "initialized", True)
    mock_rpc_device.mock_update()
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "22.9"
