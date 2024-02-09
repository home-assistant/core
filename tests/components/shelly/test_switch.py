"""Tests for Shelly switch platform."""
from copy import deepcopy
from unittest.mock import AsyncMock

from aioshelly.const import MODEL_GAS
from aioshelly.exceptions import DeviceConnectionError, InvalidAuthError, RpcCallError
import pytest

from homeassistant.components import automation, script
from homeassistant.components.automation import automations_with_entity
from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.components.script import scripts_with_entity
from homeassistant.components.shelly.const import DOMAIN, MODEL_WALL_DISPLAY
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_ICON,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
import homeassistant.helpers.issue_registry as ir
from homeassistant.setup import async_setup_component

from . import init_integration, register_entity

RELAY_BLOCK_ID = 0
GAS_VALVE_BLOCK_ID = 6


async def test_block_device_services(hass: HomeAssistant, mock_block_device) -> None:
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


async def test_block_device_unique_ids(
    hass: HomeAssistant, entity_registry, mock_block_device
) -> None:
    """Test block device unique_ids."""
    await init_integration(hass, 1)

    entry = entity_registry.async_get("switch.test_name_channel_1")
    assert entry
    assert entry.unique_id == "123456789ABC-relay_0"


async def test_block_set_state_connection_error(
    hass: HomeAssistant, mock_block_device, monkeypatch
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
    hass: HomeAssistant, mock_block_device, monkeypatch
) -> None:
    """Test block device set state authentication error."""
    monkeypatch.setattr(
        mock_block_device.blocks[RELAY_BLOCK_ID],
        "set_state",
        AsyncMock(side_effect=InvalidAuthError),
    )
    entry = await init_integration(hass, 1)

    assert entry.state == ConfigEntryState.LOADED

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.test_name_channel_1"},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert entry.state == ConfigEntryState.LOADED

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    flow = flows[0]
    assert flow.get("step_id") == "reauth_confirm"
    assert flow.get("handler") == DOMAIN

    assert "context" in flow
    assert flow["context"].get("source") == SOURCE_REAUTH
    assert flow["context"].get("entry_id") == entry.entry_id


async def test_block_device_update(
    hass: HomeAssistant, mock_block_device, monkeypatch
) -> None:
    """Test block device update."""
    monkeypatch.setattr(mock_block_device.blocks[RELAY_BLOCK_ID], "output", False)
    await init_integration(hass, 1)
    assert hass.states.get("switch.test_name_channel_1").state == STATE_OFF

    monkeypatch.setattr(mock_block_device.blocks[RELAY_BLOCK_ID], "output", True)
    mock_block_device.mock_update()
    assert hass.states.get("switch.test_name_channel_1").state == STATE_ON


async def test_block_device_no_relay_blocks(
    hass: HomeAssistant, mock_block_device, monkeypatch
) -> None:
    """Test block device without relay blocks."""
    monkeypatch.setattr(mock_block_device.blocks[RELAY_BLOCK_ID], "type", "roller")
    await init_integration(hass, 1)
    assert hass.states.get("switch.test_name_channel_1") is None


async def test_block_device_mode_roller(
    hass: HomeAssistant, mock_block_device, monkeypatch
) -> None:
    """Test block device in roller mode."""
    monkeypatch.setitem(mock_block_device.settings, "mode", "roller")
    await init_integration(hass, 1)
    assert hass.states.get("switch.test_name_channel_1") is None


async def test_block_device_app_type_light(
    hass: HomeAssistant, mock_block_device, monkeypatch
) -> None:
    """Test block device in app type set to light mode."""
    monkeypatch.setitem(
        mock_block_device.settings["relays"][RELAY_BLOCK_ID], "appliance_type", "light"
    )
    await init_integration(hass, 1)
    assert hass.states.get("switch.test_name_channel_1") is None


async def test_rpc_device_services(
    hass: HomeAssistant, mock_rpc_device, monkeypatch
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
    hass: HomeAssistant, mock_rpc_device, entity_registry
) -> None:
    """Test RPC device unique_ids."""
    await init_integration(hass, 2)

    entry = entity_registry.async_get("switch.test_switch_0")
    assert entry
    assert entry.unique_id == "123456789ABC-switch:0"


async def test_rpc_device_switch_type_lights_mode(
    hass: HomeAssistant, mock_rpc_device, monkeypatch
) -> None:
    """Test RPC device with switch in consumption type lights mode."""
    monkeypatch.setitem(
        mock_rpc_device.config["sys"]["ui_data"], "consumption_types", ["lights"]
    )
    await init_integration(hass, 2)
    assert hass.states.get("switch.test_switch_0") is None


@pytest.mark.parametrize("exc", [DeviceConnectionError, RpcCallError(-1, "error")])
async def test_rpc_set_state_errors(
    hass: HomeAssistant, exc, mock_rpc_device, monkeypatch
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
    hass: HomeAssistant, mock_rpc_device, monkeypatch
) -> None:
    """Test RPC device set state authentication error."""
    monkeypatch.setattr(
        mock_rpc_device,
        "call_rpc",
        AsyncMock(side_effect=InvalidAuthError),
    )
    entry = await init_integration(hass, 2)

    assert entry.state == ConfigEntryState.LOADED

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.test_switch_0"},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert entry.state == ConfigEntryState.LOADED

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    flow = flows[0]
    assert flow.get("step_id") == "reauth_confirm"
    assert flow.get("handler") == DOMAIN

    assert "context" in flow
    assert flow["context"].get("source") == SOURCE_REAUTH
    assert flow["context"].get("entry_id") == entry.entry_id


async def test_block_device_gas_valve(
    hass: HomeAssistant, mock_block_device, monkeypatch
) -> None:
    """Test block device Shelly Gas with Valve addon."""
    entity_id = register_entity(
        hass,
        SWITCH_DOMAIN,
        "test_name_valve",
        "valve_0-valve",
    )
    registry = er.async_get(hass)
    await init_integration(hass, 1, MODEL_GAS)

    entry = registry.async_get(entity_id)
    assert entry
    assert entry.unique_id == "123456789ABC-valve_0-valve"

    assert hass.states.get(entity_id).state == STATE_OFF  # valve is closed

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_ON  # valve is open
    assert state.attributes.get(ATTR_ICON) == "mdi:valve-open"

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OFF  # valve is closed
    assert state.attributes.get(ATTR_ICON) == "mdi:valve-closed"

    monkeypatch.setattr(mock_block_device.blocks[GAS_VALVE_BLOCK_ID], "valve", "opened")
    mock_block_device.mock_update()
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_ON  # valve is open
    assert state.attributes.get(ATTR_ICON) == "mdi:valve-open"


async def test_wall_display_thermostat_mode(
    hass: HomeAssistant,
    mock_rpc_device,
) -> None:
    """Test Wall Display in thermostat mode."""
    await init_integration(hass, 2, model=MODEL_WALL_DISPLAY)

    # the switch entity should not be created, only the climate entity
    assert hass.states.get("switch.test_name") is None
    assert hass.states.get("climate.test_name")


async def test_wall_display_relay_mode(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_rpc_device,
    monkeypatch,
) -> None:
    """Test Wall Display in thermostat mode."""
    entity_id = register_entity(
        hass,
        CLIMATE_DOMAIN,
        "test_name",
        "thermostat:0",
    )

    new_shelly = deepcopy(mock_rpc_device.shelly)
    new_shelly["relay_in_thermostat"] = False
    monkeypatch.setattr(mock_rpc_device, "shelly", new_shelly)

    await init_integration(hass, 2, model=MODEL_WALL_DISPLAY)

    # the climate entity should be removed
    assert hass.states.get(entity_id) is None


async def test_create_issue_valve_switch(
    hass: HomeAssistant,
    mock_block_device,
    entity_registry_enabled_by_default: None,
    monkeypatch,
) -> None:
    """Test we create an issue when an automation or script is using a deprecated entity."""
    monkeypatch.setitem(mock_block_device.status, "cloud", {"connected": False})
    entity_id = register_entity(
        hass,
        SWITCH_DOMAIN,
        "test_name_valve",
        "valve_0-valve",
    )

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "alias": "test",
                "trigger": {"platform": "state", "entity_id": entity_id},
                "action": {"service": "switch.turn_on", "entity_id": entity_id},
            }
        },
    )
    assert await async_setup_component(
        hass,
        script.DOMAIN,
        {
            script.DOMAIN: {
                "test": {
                    "sequence": [
                        {
                            "service": "switch.turn_on",
                            "data": {"entity_id": entity_id},
                        },
                    ],
                }
            }
        },
    )

    await init_integration(hass, 1, MODEL_GAS)

    assert automations_with_entity(hass, entity_id)[0] == "automation.test"
    assert scripts_with_entity(hass, entity_id)[0] == "script.test"
    issue_registry: ir.IssueRegistry = ir.async_get(hass)

    assert issue_registry.async_get_issue(DOMAIN, "deprecated_valve_switch")
    assert issue_registry.async_get_issue(
        DOMAIN, "deprecated_valve_switch.test_name_valve_automation.test"
    )
    assert issue_registry.async_get_issue(
        DOMAIN, "deprecated_valve_switch.test_name_valve_script.test"
    )

    assert len(issue_registry.issues) == 3
