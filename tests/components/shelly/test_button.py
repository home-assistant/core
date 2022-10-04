"""Tests for Shelly button platform."""
from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.shelly.const import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import async_get


async def test_block_button(hass: HomeAssistant, coap_wrapper):
    """Test block device reboot button."""
    assert coap_wrapper

    entity_registry = async_get(hass)
    entity_registry.async_get_or_create(
        BUTTON_DOMAIN,
        DOMAIN,
        "test_name_reboot",
        suggested_object_id="test_name_reboot",
        disabled_by=None,
    )
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(coap_wrapper.entry, BUTTON_DOMAIN)
    )
    await hass.async_block_till_done()

    # reboot button
    state = hass.states.get("button.test_name_reboot")

    assert state
    assert state.state == STATE_UNKNOWN

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.test_name_reboot"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert coap_wrapper.device.trigger_reboot.call_count == 1


async def test_rpc_button(hass: HomeAssistant, rpc_wrapper):
    """Test rpc device OTA button."""
    assert rpc_wrapper

    entity_registry = async_get(hass)
    entity_registry.async_get_or_create(
        BUTTON_DOMAIN,
        DOMAIN,
        "test_name_reboot",
        suggested_object_id="test_name_reboot",
        disabled_by=None,
    )

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(rpc_wrapper.entry, BUTTON_DOMAIN)
    )
    await hass.async_block_till_done()

    # reboot button
    state = hass.states.get("button.test_name_reboot")

    assert state
    assert state.state == STATE_UNKNOWN

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.test_name_reboot"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert rpc_wrapper.device.trigger_reboot.call_count == 1
