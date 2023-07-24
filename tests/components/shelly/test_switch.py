"""Tests for Shelly switch platform."""
from unittest.mock import AsyncMock

from aioshelly.exceptions import DeviceConnectionError, InvalidAuthError, RpcCallError
import pytest

from homeassistant.components.shelly.const import DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import init_integration

RELAY_BLOCK_ID = 0


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
