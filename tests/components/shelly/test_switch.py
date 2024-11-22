"""Tests for Shelly switch platform."""

from copy import deepcopy
from unittest.mock import AsyncMock, Mock

from aioshelly.const import MODEL_GAS
from aioshelly.exceptions import DeviceConnectionError, InvalidAuthError, RpcCallError
import pytest

from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.components.shelly.const import (
    DOMAIN,
    MODEL_WALL_DISPLAY,
    MOTION_MODELS,
)
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceRegistry
from homeassistant.helpers.entity_registry import EntityRegistry

from . import get_entity_state, init_integration, register_device, register_entity

from tests.common import mock_restore_cache

RELAY_BLOCK_ID = 0
GAS_VALVE_BLOCK_ID = 6
MOTION_BLOCK_ID = 3


async def test_block_device_services(
    hass: HomeAssistant, mock_block_device: Mock
) -> None:
    """Test block device turn on/off services."""
    await init_integration(hass, 1)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.test_name_channel_1"},
        blocking=True,
    )
    assert hass.states.get("switch.test_name_channel_1").state == STATE_ON

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.test_name_channel_1"},
        blocking=True,
    )
    assert hass.states.get("switch.test_name_channel_1").state == STATE_OFF


@pytest.mark.parametrize("model", MOTION_MODELS)
async def test_block_motion_switch(
    hass: HomeAssistant,
    model: str,
    mock_block_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test Shelly motion active turn on/off services."""
    entity_id = "switch.test_name_motion_detection"
    await init_integration(hass, 1, sleep_period=1000, model=model)

    # Make device online
    mock_block_device.mock_online()
    await hass.async_block_till_done(wait_background_tasks=True)

    assert get_entity_state(hass, entity_id) == STATE_ON

    # turn off
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    monkeypatch.setattr(mock_block_device.blocks[MOTION_BLOCK_ID], "motionActive", 0)
    mock_block_device.mock_update()

    mock_block_device.set_shelly_motion_detection.assert_called_once_with(False)
    assert get_entity_state(hass, entity_id) == STATE_OFF

    # turn on
    mock_block_device.set_shelly_motion_detection.reset_mock()
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    monkeypatch.setattr(mock_block_device.blocks[MOTION_BLOCK_ID], "motionActive", 1)
    mock_block_device.mock_update()

    mock_block_device.set_shelly_motion_detection.assert_called_once_with(True)
    assert get_entity_state(hass, entity_id) == STATE_ON


@pytest.mark.parametrize("model", MOTION_MODELS)
async def test_block_restored_motion_switch(
    hass: HomeAssistant,
    model: str,
    mock_block_device: Mock,
    device_registry: DeviceRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test block restored motion active switch."""
    entry = await init_integration(
        hass, 1, sleep_period=1000, model=model, skip_setup=True
    )
    device = register_device(device_registry, entry)
    entity_id = register_entity(
        hass,
        SWITCH_DOMAIN,
        "test_name_motion_detection",
        "sensor_0-motionActive",
        entry,
        device_id=device.id,
    )

    mock_restore_cache(hass, [State(entity_id, STATE_OFF)])
    monkeypatch.setattr(mock_block_device, "initialized", False)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert get_entity_state(hass, entity_id) == STATE_OFF

    # Make device online
    monkeypatch.setattr(mock_block_device, "initialized", True)
    mock_block_device.mock_online()
    await hass.async_block_till_done(wait_background_tasks=True)

    assert get_entity_state(hass, entity_id) == STATE_ON


@pytest.mark.parametrize("model", MOTION_MODELS)
async def test_block_restored_motion_switch_no_last_state(
    hass: HomeAssistant,
    model: str,
    mock_block_device: Mock,
    device_registry: DeviceRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test block restored motion active switch missing last state."""
    entry = await init_integration(
        hass, 1, sleep_period=1000, model=model, skip_setup=True
    )
    device = register_device(device_registry, entry)
    entity_id = register_entity(
        hass,
        SWITCH_DOMAIN,
        "test_name_motion_detection",
        "sensor_0-motionActive",
        entry,
        device_id=device.id,
    )
    monkeypatch.setattr(mock_block_device, "initialized", False)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert get_entity_state(hass, entity_id) == STATE_UNKNOWN

    # Make device online
    monkeypatch.setattr(mock_block_device, "initialized", True)
    mock_block_device.mock_online()
    await hass.async_block_till_done(wait_background_tasks=True)

    assert get_entity_state(hass, entity_id) == STATE_ON


async def test_block_device_unique_ids(
    hass: HomeAssistant, entity_registry: EntityRegistry, mock_block_device: Mock
) -> None:
    """Test block device unique_ids."""
    await init_integration(hass, 1)

    entry = entity_registry.async_get("switch.test_name_channel_1")
    assert entry
    assert entry.unique_id == "123456789ABC-relay_0"


async def test_block_set_state_connection_error(
    hass: HomeAssistant, mock_block_device, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test block device set state connection error."""
    monkeypatch.setattr(
        mock_block_device.blocks[RELAY_BLOCK_ID],
        "set_state",
        AsyncMock(side_effect=DeviceConnectionError),
    )
    await init_integration(hass, 1)

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "switch.test_name_channel_1"},
            blocking=True,
        )


async def test_block_set_state_auth_error(
    hass: HomeAssistant, mock_block_device: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test block device set state authentication error."""
    monkeypatch.setattr(
        mock_block_device.blocks[RELAY_BLOCK_ID],
        "set_state",
        AsyncMock(side_effect=InvalidAuthError),
    )
    entry = await init_integration(hass, 1)

    assert entry.state is ConfigEntryState.LOADED

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.test_name_channel_1"},
        blocking=True,
    )

    assert entry.state is ConfigEntryState.LOADED

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    flow = flows[0]
    assert flow.get("step_id") == "reauth_confirm"
    assert flow.get("handler") == DOMAIN

    assert "context" in flow
    assert flow["context"].get("source") == SOURCE_REAUTH
    assert flow["context"].get("entry_id") == entry.entry_id


async def test_block_device_update(
    hass: HomeAssistant, mock_block_device: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test block device update."""
    monkeypatch.setattr(mock_block_device.blocks[RELAY_BLOCK_ID], "output", False)
    await init_integration(hass, 1)
    assert hass.states.get("switch.test_name_channel_1").state == STATE_OFF

    monkeypatch.setattr(mock_block_device.blocks[RELAY_BLOCK_ID], "output", True)
    mock_block_device.mock_update()
    assert hass.states.get("switch.test_name_channel_1").state == STATE_ON


async def test_block_device_no_relay_blocks(
    hass: HomeAssistant, mock_block_device: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test block device without relay blocks."""
    monkeypatch.setattr(mock_block_device.blocks[RELAY_BLOCK_ID], "type", "roller")
    await init_integration(hass, 1)
    assert hass.states.get("switch.test_name_channel_1") is None


async def test_block_device_mode_roller(
    hass: HomeAssistant, mock_block_device: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test block device in roller mode."""
    monkeypatch.setitem(mock_block_device.settings, "mode", "roller")
    await init_integration(hass, 1)
    assert hass.states.get("switch.test_name_channel_1") is None


async def test_block_device_app_type_light(
    hass: HomeAssistant, mock_block_device: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test block device in app type set to light mode."""
    monkeypatch.setitem(
        mock_block_device.settings["relays"][RELAY_BLOCK_ID], "appliance_type", "light"
    )
    await init_integration(hass, 1)
    assert hass.states.get("switch.test_name_channel_1") is None


async def test_rpc_device_services(
    hass: HomeAssistant, mock_rpc_device: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test RPC device turn on/off services."""
    await init_integration(hass, 2)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.test_switch_0"},
        blocking=True,
    )
    assert hass.states.get("switch.test_switch_0").state == STATE_ON

    monkeypatch.setitem(mock_rpc_device.status["switch:0"], "output", False)
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.test_switch_0"},
        blocking=True,
    )
    mock_rpc_device.mock_update()
    assert hass.states.get("switch.test_switch_0").state == STATE_OFF


async def test_rpc_device_unique_ids(
    hass: HomeAssistant, mock_rpc_device: Mock, entity_registry: EntityRegistry
) -> None:
    """Test RPC device unique_ids."""
    await init_integration(hass, 2)

    entry = entity_registry.async_get("switch.test_switch_0")
    assert entry
    assert entry.unique_id == "123456789ABC-switch:0"


async def test_rpc_device_switch_type_lights_mode(
    hass: HomeAssistant, mock_rpc_device: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test RPC device with switch in consumption type lights mode."""
    monkeypatch.setitem(
        mock_rpc_device.config["sys"]["ui_data"], "consumption_types", ["lights"]
    )
    await init_integration(hass, 2)
    assert hass.states.get("switch.test_switch_0") is None


@pytest.mark.parametrize("exc", [DeviceConnectionError, RpcCallError(-1, "error")])
async def test_rpc_set_state_errors(
    hass: HomeAssistant,
    exc: Exception,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test RPC device set state connection/call errors."""
    monkeypatch.setattr(mock_rpc_device, "call_rpc", AsyncMock(side_effect=exc))
    await init_integration(hass, 2)

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "switch.test_switch_0"},
            blocking=True,
        )


async def test_rpc_auth_error(
    hass: HomeAssistant, mock_rpc_device: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test RPC device set state authentication error."""
    monkeypatch.setattr(
        mock_rpc_device,
        "call_rpc",
        AsyncMock(side_effect=InvalidAuthError),
    )
    entry = await init_integration(hass, 2)

    assert entry.state is ConfigEntryState.LOADED

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.test_switch_0"},
        blocking=True,
    )

    assert entry.state is ConfigEntryState.LOADED

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    flow = flows[0]
    assert flow.get("step_id") == "reauth_confirm"
    assert flow.get("handler") == DOMAIN

    assert "context" in flow
    assert flow["context"].get("source") == SOURCE_REAUTH
    assert flow["context"].get("entry_id") == entry.entry_id


async def test_remove_gas_valve_switch(
    hass: HomeAssistant,
    mock_block_device: Mock,
    entity_registry: EntityRegistry,
) -> None:
    """Test removing deprecated switch entity for Shelly Gas Valve."""
    entity_id = register_entity(
        hass,
        SWITCH_DOMAIN,
        "test_name_valve",
        "valve_0-valve",
    )
    await init_integration(hass, 1, MODEL_GAS)

    assert entity_registry.async_get(entity_id) is None


async def test_wall_display_relay_mode(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    entity_registry: EntityRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test Wall Display in relay mode."""
    climate_entity_id = "climate.test_name"
    switch_entity_id = "switch.test_switch_0"

    new_status = deepcopy(mock_rpc_device.status)
    new_status["sys"]["relay_in_thermostat"] = False
    new_status.pop("thermostat:0")
    monkeypatch.setattr(mock_rpc_device, "status", new_status)

    await init_integration(hass, 2, model=MODEL_WALL_DISPLAY)

    # the climate entity should be removed
    assert hass.states.get(climate_entity_id) is None
    assert len(hass.states.async_entity_ids(CLIMATE_DOMAIN)) == 0

    # the switch entity should be created
    state = hass.states.get(switch_entity_id)
    assert state
    assert state.state == STATE_ON
    assert len(hass.states.async_entity_ids(SWITCH_DOMAIN)) == 1

    entry = entity_registry.async_get(switch_entity_id)
    assert entry
    assert entry.unique_id == "123456789ABC-switch:0"


@pytest.mark.parametrize(
    ("name", "entity_id"),
    [
        ("Virtual switch", "switch.test_name_virtual_switch"),
        (None, "switch.test_name_boolean_200"),
    ],
)
async def test_rpc_device_virtual_switch(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
    name: str | None,
    entity_id: str,
) -> None:
    """Test a virtual switch for RPC device."""
    config = deepcopy(mock_rpc_device.config)
    config["boolean:200"] = {
        "name": name,
        "meta": {"ui": {"view": "toggle"}},
    }
    monkeypatch.setattr(mock_rpc_device, "config", config)

    status = deepcopy(mock_rpc_device.status)
    status["boolean:200"] = {"value": True}
    monkeypatch.setattr(mock_rpc_device, "status", status)

    await init_integration(hass, 3)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_ON

    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "123456789ABC-boolean:200-boolean"

    monkeypatch.setitem(mock_rpc_device.status["boolean:200"], "value", False)
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    mock_rpc_device.mock_update()
    assert hass.states.get(entity_id).state == STATE_OFF

    monkeypatch.setitem(mock_rpc_device.status["boolean:200"], "value", True)
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    mock_rpc_device.mock_update()
    assert hass.states.get(entity_id).state == STATE_ON


async def test_rpc_device_virtual_binary_sensor(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that a switch entity has not been created for a virtual binary sensor."""
    config = deepcopy(mock_rpc_device.config)
    config["boolean:200"] = {"name": None, "meta": {"ui": {"view": "label"}}}
    monkeypatch.setattr(mock_rpc_device, "config", config)

    status = deepcopy(mock_rpc_device.status)
    status["boolean:200"] = {"value": True}
    monkeypatch.setattr(mock_rpc_device, "status", status)

    entity_id = "switch.test_name_boolean_200"

    await init_integration(hass, 3)

    state = hass.states.get(entity_id)
    assert not state


async def test_rpc_remove_virtual_switch_when_mode_label(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: DeviceRegistry,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test if the virtual switch will be removed if the mode has been changed to a label."""
    config = deepcopy(mock_rpc_device.config)
    config["boolean:200"] = {"name": None, "meta": {"ui": {"view": "label"}}}
    monkeypatch.setattr(mock_rpc_device, "config", config)

    status = deepcopy(mock_rpc_device.status)
    status["boolean:200"] = {"value": True}
    monkeypatch.setattr(mock_rpc_device, "status", status)

    config_entry = await init_integration(hass, 3, skip_setup=True)
    device_entry = register_device(device_registry, config_entry)
    entity_id = register_entity(
        hass,
        SWITCH_DOMAIN,
        "test_name_boolean_200",
        "boolean:200-boolean",
        config_entry,
        device_id=device_entry.id,
    )

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    entry = entity_registry.async_get(entity_id)
    assert not entry


async def test_rpc_remove_virtual_switch_when_orphaned(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: DeviceRegistry,
    mock_rpc_device: Mock,
) -> None:
    """Check whether the virtual switch will be removed if it has been removed from the device configuration."""
    config_entry = await init_integration(hass, 3, skip_setup=True)
    device_entry = register_device(device_registry, config_entry)
    entity_id = register_entity(
        hass,
        SWITCH_DOMAIN,
        "test_name_boolean_200",
        "boolean:200-boolean",
        config_entry,
        device_id=device_entry.id,
    )

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    entry = entity_registry.async_get(entity_id)
    assert not entry


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_rpc_device_script_switch(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test a script switch for RPC device."""
    config = deepcopy(mock_rpc_device.config)
    key = "script:1"
    script_name = "aioshelly_ble_integration"
    entity_id = f"switch.test_name_{script_name}"
    config[key] = {
        "id": 1,
        "name": script_name,
        "enable": False,
    }
    monkeypatch.setattr(mock_rpc_device, "config", config)

    status = deepcopy(mock_rpc_device.status)
    status[key] = {
        "running": True,
    }
    monkeypatch.setattr(mock_rpc_device, "status", status)

    await init_integration(hass, 3)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_ON
    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == f"123456789ABC-{key}-script"

    monkeypatch.setitem(mock_rpc_device.status[key], "running", False)
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    mock_rpc_device.mock_update()
    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OFF

    monkeypatch.setitem(mock_rpc_device.status[key], "running", True)
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    mock_rpc_device.mock_update()
    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_ON
