"""The scene tests for the myq platform."""
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)

RELAY_BLOCK_ID = 0


async def test_services(hass, coap_wrapper):
    """Test device turn on/off services."""
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


async def test_update(hass, coap_wrapper, monkeypatch):
    """Test device update."""
    assert coap_wrapper

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(coap_wrapper.entry, SWITCH_DOMAIN)
    )
    await hass.async_block_till_done()

    monkeypatch.setattr(coap_wrapper.device.blocks[RELAY_BLOCK_ID], "output", False)
    await hass.helpers.entity_component.async_update_entity(
        "switch.test_name_channel_1"
    )
    await hass.async_block_till_done()
    assert hass.states.get("switch.test_name_channel_1").state == STATE_OFF

    monkeypatch.setattr(coap_wrapper.device.blocks[RELAY_BLOCK_ID], "output", True)
    await hass.helpers.entity_component.async_update_entity(
        "switch.test_name_channel_1"
    )
    await hass.async_block_till_done()
    assert hass.states.get("switch.test_name_channel_1").state == STATE_ON


async def test_no_relay_blocks(hass, coap_wrapper, monkeypatch):
    """Test device without relay blocks."""
    assert coap_wrapper

    monkeypatch.setattr(coap_wrapper.device.blocks[RELAY_BLOCK_ID], "type", "roller")
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(coap_wrapper.entry, SWITCH_DOMAIN)
    )
    await hass.async_block_till_done()
    assert hass.states.get("switch.test_name_channel_1") is None


async def test_device_mode_roller(hass, coap_wrapper, monkeypatch):
    """Test switch device in roller mode."""
    assert coap_wrapper

    monkeypatch.setitem(coap_wrapper.device.settings, "mode", "roller")
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(coap_wrapper.entry, SWITCH_DOMAIN)
    )
    await hass.async_block_till_done()
    assert hass.states.get("switch.test_name_channel_1") is None
