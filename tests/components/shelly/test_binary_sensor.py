"""Tests for Shelly binary sensor platform."""

from copy import deepcopy
from unittest.mock import Mock

from aioshelly.const import MODEL_MOTION
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.shelly.const import UPDATE_PERIOD_MULTIPLIER
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceRegistry
from homeassistant.helpers.entity_registry import EntityRegistry

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
    hass: HomeAssistant,
    mock_block_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
    entity_registry: EntityRegistry,
) -> None:
    """Test block binary sensor."""
    entity_id = f"{BINARY_SENSOR_DOMAIN}.test_name_channel_1_overpowering"
    await init_integration(hass, 1)

    assert hass.states.get(entity_id).state == STATE_OFF

    monkeypatch.setattr(mock_block_device.blocks[RELAY_BLOCK_ID], "overpower", 1)
    mock_block_device.mock_update()

    assert hass.states.get(entity_id).state == STATE_ON

    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "123456789ABC-relay_0-overpower"


async def test_block_binary_sensor_extra_state_attr(
    hass: HomeAssistant,
    mock_block_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
    entity_registry: EntityRegistry,
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

    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "123456789ABC-sensor_0-gas"


async def test_block_rest_binary_sensor(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_block_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
    entity_registry: EntityRegistry,
) -> None:
    """Test block REST binary sensor."""
    entity_id = register_entity(hass, BINARY_SENSOR_DOMAIN, "test_name_cloud", "cloud")
    monkeypatch.setitem(mock_block_device.status, "cloud", {"connected": False})
    await init_integration(hass, 1)

    assert hass.states.get(entity_id).state == STATE_OFF

    monkeypatch.setitem(mock_block_device.status["cloud"], "connected", True)
    await mock_rest_update(hass, freezer)

    assert hass.states.get(entity_id).state == STATE_ON

    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "123456789ABC-cloud"


async def test_block_rest_binary_sensor_connected_battery_devices(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_block_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
    entity_registry: EntityRegistry,
) -> None:
    """Test block REST binary sensor for connected battery devices."""
    entity_id = register_entity(hass, BINARY_SENSOR_DOMAIN, "test_name_cloud", "cloud")
    monkeypatch.setitem(mock_block_device.status, "cloud", {"connected": False})
    monkeypatch.setitem(mock_block_device.settings["device"], "type", MODEL_MOTION)
    monkeypatch.setitem(mock_block_device.settings["coiot"], "update_period", 3600)
    await init_integration(hass, 1, model=MODEL_MOTION)

    assert hass.states.get(entity_id).state == STATE_OFF

    monkeypatch.setitem(mock_block_device.status["cloud"], "connected", True)

    # Verify no update on fast intervals
    await mock_rest_update(hass, freezer)
    assert hass.states.get(entity_id).state == STATE_OFF

    # Verify update on slow intervals
    await mock_rest_update(hass, freezer, seconds=UPDATE_PERIOD_MULTIPLIER * 3600)
    assert hass.states.get(entity_id).state == STATE_ON

    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "123456789ABC-cloud"


async def test_block_sleeping_binary_sensor(
    hass: HomeAssistant,
    mock_block_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
    entity_registry: EntityRegistry,
) -> None:
    """Test block sleeping binary sensor."""
    entity_id = f"{BINARY_SENSOR_DOMAIN}.test_name_motion"
    await init_integration(hass, 1, sleep_period=1000)

    # Sensor should be created when device is online
    assert hass.states.get(entity_id) is None

    # Make device online
    mock_block_device.mock_online()
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(entity_id).state == STATE_OFF

    monkeypatch.setattr(mock_block_device.blocks[SENSOR_BLOCK_ID], "motion", 1)
    mock_block_device.mock_update()

    assert hass.states.get(entity_id).state == STATE_ON

    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "123456789ABC-sensor_0-motion"


async def test_block_restored_sleeping_binary_sensor(
    hass: HomeAssistant,
    mock_block_device: Mock,
    device_registry: DeviceRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test block restored sleeping binary sensor."""
    entry = await init_integration(hass, 1, sleep_period=1000, skip_setup=True)
    device = register_device(device_registry, entry)
    entity_id = register_entity(
        hass,
        BINARY_SENSOR_DOMAIN,
        "test_name_motion",
        "sensor_0-motion",
        entry,
        device_id=device.id,
    )
    mock_restore_cache(hass, [State(entity_id, STATE_ON)])
    monkeypatch.setattr(mock_block_device, "initialized", False)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_ON

    # Make device online
    monkeypatch.setattr(mock_block_device, "initialized", True)
    mock_block_device.mock_online()
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(entity_id).state == STATE_OFF


async def test_block_restored_sleeping_binary_sensor_no_last_state(
    hass: HomeAssistant,
    mock_block_device: Mock,
    device_registry: DeviceRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test block restored sleeping binary sensor missing last state."""
    entry = await init_integration(hass, 1, sleep_period=1000, skip_setup=True)
    device = register_device(device_registry, entry)
    entity_id = register_entity(
        hass,
        BINARY_SENSOR_DOMAIN,
        "test_name_motion",
        "sensor_0-motion",
        entry,
        device_id=device.id,
    )
    monkeypatch.setattr(mock_block_device, "initialized", False)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_UNKNOWN

    # Make device online
    monkeypatch.setattr(mock_block_device, "initialized", True)
    mock_block_device.mock_online()
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(entity_id).state == STATE_OFF


async def test_rpc_binary_sensor(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
    entity_registry: EntityRegistry,
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

    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "123456789ABC-cover:0-overpower"


async def test_rpc_binary_sensor_removal(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
    entity_registry: EntityRegistry,
) -> None:
    """Test RPC binary sensor is removed due to removal_condition."""
    entity_id = register_entity(
        hass, BINARY_SENSOR_DOMAIN, "test_cover_0_input", "input:0-input"
    )

    assert entity_registry.async_get(entity_id) is not None

    monkeypatch.setattr(mock_rpc_device, "status", {"input:0": {"state": False}})
    await init_integration(hass, 2)

    assert entity_registry.async_get(entity_id) is None


async def test_rpc_sleeping_binary_sensor(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
    entity_registry: EntityRegistry,
) -> None:
    """Test RPC online sleeping binary sensor."""
    entity_id = f"{BINARY_SENSOR_DOMAIN}.test_name_cloud"
    monkeypatch.setattr(mock_rpc_device, "connected", False)
    monkeypatch.setitem(mock_rpc_device.status["sys"], "wakeup_period", 1000)
    config_entry = await init_integration(hass, 2, sleep_period=1000)

    # Sensor should be created when device is online
    assert hass.states.get(entity_id) is None

    register_entity(
        hass, BINARY_SENSOR_DOMAIN, "test_name_cloud", "cloud-cloud", config_entry
    )

    # Make device online
    mock_rpc_device.mock_online()
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(entity_id).state == STATE_OFF

    mutate_rpc_device_status(monkeypatch, mock_rpc_device, "cloud", "connected", True)
    mock_rpc_device.mock_update()

    assert hass.states.get(entity_id).state == STATE_ON

    # test external power sensor
    state = hass.states.get("binary_sensor.test_name_external_power")
    assert state
    assert state.state == STATE_ON

    entry = entity_registry.async_get("binary_sensor.test_name_external_power")
    assert entry
    assert entry.unique_id == "123456789ABC-devicepower:0-external_power"


async def test_rpc_restored_sleeping_binary_sensor(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    device_registry: DeviceRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test RPC restored binary sensor."""
    entry = await init_integration(hass, 2, sleep_period=1000, skip_setup=True)
    device = register_device(device_registry, entry)
    entity_id = register_entity(
        hass,
        BINARY_SENSOR_DOMAIN,
        "test_name_cloud",
        "cloud-cloud",
        entry,
        device_id=device.id,
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
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    device_registry: DeviceRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test RPC restored sleeping binary sensor missing last state."""
    entry = await init_integration(hass, 2, sleep_period=1000, skip_setup=True)
    device = register_device(device_registry, entry)
    entity_id = register_entity(
        hass,
        BINARY_SENSOR_DOMAIN,
        "test_name_cloud",
        "cloud-cloud",
        entry,
        device_id=device.id,
    )

    monkeypatch.setattr(mock_rpc_device, "initialized", False)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_UNKNOWN

    # Make device online
    monkeypatch.setattr(mock_rpc_device, "initialized", True)
    mock_rpc_device.mock_online()
    await hass.async_block_till_done(wait_background_tasks=True)

    # Mock update
    mock_rpc_device.mock_update()
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_OFF


@pytest.mark.parametrize(
    ("name", "entity_id"),
    [
        ("Virtual binary sensor", "binary_sensor.test_name_virtual_binary_sensor"),
        (None, "binary_sensor.test_name_boolean_203"),
    ],
)
async def test_rpc_device_virtual_binary_sensor(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
    name: str | None,
    entity_id: str,
) -> None:
    """Test a virtual binary sensor for RPC device."""
    config = deepcopy(mock_rpc_device.config)
    config["boolean:203"] = {
        "name": name,
        "meta": {"ui": {"view": "label"}},
    }
    monkeypatch.setattr(mock_rpc_device, "config", config)

    status = deepcopy(mock_rpc_device.status)
    status["boolean:203"] = {"value": True}
    monkeypatch.setattr(mock_rpc_device, "status", status)

    await init_integration(hass, 3)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_ON

    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "123456789ABC-boolean:203-boolean"

    monkeypatch.setitem(mock_rpc_device.status["boolean:203"], "value", False)
    mock_rpc_device.mock_update()
    assert hass.states.get(entity_id).state == STATE_OFF


async def test_rpc_remove_virtual_binary_sensor_when_mode_toggle(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: DeviceRegistry,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test if the virtual binary sensor will be removed if the mode has been changed to a toggle."""
    config = deepcopy(mock_rpc_device.config)
    config["boolean:200"] = {"name": None, "meta": {"ui": {"view": "toggle"}}}
    monkeypatch.setattr(mock_rpc_device, "config", config)

    status = deepcopy(mock_rpc_device.status)
    status["boolean:200"] = {"value": True}
    monkeypatch.setattr(mock_rpc_device, "status", status)

    config_entry = await init_integration(hass, 3, skip_setup=True)
    device_entry = register_device(device_registry, config_entry)
    entity_id = register_entity(
        hass,
        BINARY_SENSOR_DOMAIN,
        "test_name_boolean_200",
        "boolean:200-boolean",
        config_entry,
        device_id=device_entry.id,
    )

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    entry = entity_registry.async_get(entity_id)
    assert not entry


async def test_rpc_remove_virtual_binary_sensor_when_orphaned(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: DeviceRegistry,
    mock_rpc_device: Mock,
) -> None:
    """Check whether the virtual binary sensor will be removed if it has been removed from the device configuration."""
    config_entry = await init_integration(hass, 3, skip_setup=True)
    device_entry = register_device(device_registry, config_entry)
    entity_id = register_entity(
        hass,
        BINARY_SENSOR_DOMAIN,
        "test_name_boolean_200",
        "boolean:200-boolean",
        config_entry,
        device_id=device_entry.id,
    )

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    entry = entity_registry.async_get(entity_id)
    assert not entry
