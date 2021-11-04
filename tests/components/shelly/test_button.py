"""The scene tests for the myq platform."""
from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN
from homeassistant.components.button.const import SERVICE_PRESS
from homeassistant.components.shelly.service import async_services_setup
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN
from homeassistant.core import HomeAssistant


async def test_block_button(hass: HomeAssistant, coap_wrapper):
    """Test block device OTA button."""
    assert coap_wrapper

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(coap_wrapper.entry, BUTTON_DOMAIN)
    )
    await hass.async_block_till_done()

    state = hass.states.get("button.test_name_ota_update")
    assert state
    assert state.state == STATE_UNKNOWN

    await async_services_setup(hass)
    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.test_name_ota_update"},
        blocking=True,
    )
    await hass.async_block_till_done()
    coap_wrapper.device.trigger_ota_update.assert_called_once()


async def test_rpc_button(hass: HomeAssistant, rpc_wrapper):
    """Test rpc device OTA button."""
    assert rpc_wrapper

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(rpc_wrapper.entry, BUTTON_DOMAIN)
    )
    await hass.async_block_till_done()

    state = hass.states.get("button.test_name_ota_update")
    assert state
    assert state.state == STATE_UNKNOWN

    await async_services_setup(hass)
    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.test_name_ota_update"},
        blocking=True,
    )
    await hass.async_block_till_done()
    rpc_wrapper.device.trigger_ota_update.assert_called_once()
