"""Tests for Shelly switch platform."""
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)

from . import init_integration

RELAY_BLOCK_ID = 0


async def test_block_device_services(hass, mock_block_device):
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


async def test_block_device_update(hass, mock_block_device, monkeypatch):
    """Test block device update."""
    monkeypatch.setattr(mock_block_device.blocks[RELAY_BLOCK_ID], "output", False)
    await init_integration(hass, 1)
    assert hass.states.get("switch.test_name_channel_1").state == STATE_OFF

    monkeypatch.setattr(mock_block_device.blocks[RELAY_BLOCK_ID], "output", True)
    mock_block_device.mock_update()
    assert hass.states.get("switch.test_name_channel_1").state == STATE_ON


async def test_block_device_no_relay_blocks(hass, mock_block_device, monkeypatch):
    """Test block device without relay blocks."""
    monkeypatch.setattr(mock_block_device.blocks[RELAY_BLOCK_ID], "type", "roller")
    await init_integration(hass, 1)
    assert hass.states.get("switch.test_name_channel_1") is None


async def test_block_device_mode_roller(hass, mock_block_device, monkeypatch):
    """Test block device in roller mode."""
    monkeypatch.setitem(mock_block_device.settings, "mode", "roller")
    await init_integration(hass, 1)
    assert hass.states.get("switch.test_name_channel_1") is None


async def test_block_device_app_type_light(hass, mock_block_device, monkeypatch):
    """Test block device in app type set to light mode."""
    monkeypatch.setitem(
        mock_block_device.settings["relays"][RELAY_BLOCK_ID], "appliance_type", "light"
    )
    await init_integration(hass, 1)
    assert hass.states.get("switch.test_name_channel_1") is None


async def test_rpc_device_services(hass, mock_rpc_device, monkeypatch):
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


async def test_rpc_device_switch_type_lights_mode(hass, mock_rpc_device, monkeypatch):
    """Test RPC device with switch in consumption type lights mode."""
    monkeypatch.setitem(
        mock_rpc_device.config["sys"]["ui_data"], "consumption_types", ["lights"]
    )
    await init_integration(hass, 2)
    assert hass.states.get("switch.test_switch_0") is None
