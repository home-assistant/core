"""The scene tests for the myq platform."""
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.helpers.entity_component import async_update_entity

RELAY_BLOCK_ID = 0


async def test_block_device_services(hass, coap_wrapper):
    """Test block device turn on/off services."""
    assert coap_wrapper

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(coap_wrapper.entry, SWITCH_DOMAIN)
    )
    await hass.async_block_till_done()

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


async def test_block_device_update(hass, coap_wrapper, monkeypatch):
    """Test block device update."""
    assert coap_wrapper

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(coap_wrapper.entry, SWITCH_DOMAIN)
    )
    await hass.async_block_till_done()

    monkeypatch.setattr(coap_wrapper.device.blocks[RELAY_BLOCK_ID], "output", False)
    await async_update_entity(hass, "switch.test_name_channel_1")
    await hass.async_block_till_done()
    assert hass.states.get("switch.test_name_channel_1").state == STATE_OFF

    monkeypatch.setattr(coap_wrapper.device.blocks[RELAY_BLOCK_ID], "output", True)
    await async_update_entity(hass, "switch.test_name_channel_1")
    await hass.async_block_till_done()
    assert hass.states.get("switch.test_name_channel_1").state == STATE_ON


async def test_block_device_no_relay_blocks(hass, coap_wrapper, monkeypatch):
    """Test block device without relay blocks."""
    assert coap_wrapper

    monkeypatch.setattr(coap_wrapper.device.blocks[RELAY_BLOCK_ID], "type", "roller")
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(coap_wrapper.entry, SWITCH_DOMAIN)
    )
    await hass.async_block_till_done()
    assert hass.states.get("switch.test_name_channel_1") is None


async def test_block_device_mode_roller(hass, coap_wrapper, monkeypatch):
    """Test block device in roller mode."""
    assert coap_wrapper

    monkeypatch.setitem(coap_wrapper.device.settings, "mode", "roller")
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(coap_wrapper.entry, SWITCH_DOMAIN)
    )
    await hass.async_block_till_done()
    assert hass.states.get("switch.test_name_channel_1") is None


async def test_block_device_app_type_light(hass, coap_wrapper, monkeypatch):
    """Test block device in app type set to light mode."""
    assert coap_wrapper

    monkeypatch.setitem(
        coap_wrapper.device.settings["relays"][0], "appliance_type", "light"
    )
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(coap_wrapper.entry, SWITCH_DOMAIN)
    )
    await hass.async_block_till_done()
    assert hass.states.get("switch.test_name_channel_1") is None


async def test_rpc_device_services(hass, rpc_wrapper, monkeypatch):
    """Test RPC device turn on/off services."""
    assert rpc_wrapper

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(rpc_wrapper.entry, SWITCH_DOMAIN)
    )
    await hass.async_block_till_done()

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.test_switch_0"},
        blocking=True,
    )
    assert hass.states.get("switch.test_switch_0").state == STATE_ON

    monkeypatch.setitem(rpc_wrapper.device.status["switch:0"], "output", False)
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.test_switch_0"},
        blocking=True,
    )
    rpc_wrapper.async_set_updated_data("")
    assert hass.states.get("switch.test_switch_0").state == STATE_OFF


async def test_rpc_device_switch_type_lights_mode(hass, rpc_wrapper, monkeypatch):
    """Test RPC device with switch in consumption type lights mode."""
    assert rpc_wrapper

    monkeypatch.setitem(
        rpc_wrapper.device.config["sys"]["ui_data"],
        "consumption_types",
        ["lights"],
    )
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(rpc_wrapper.entry, SWITCH_DOMAIN)
    )
    await hass.async_block_till_done()
    assert hass.states.get("switch.test_switch_0") is None
