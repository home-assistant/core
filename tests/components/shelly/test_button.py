"""Tests for Shelly button platform."""
import pytest

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN
from homeassistant.components.button.const import SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN
from homeassistant.core import HomeAssistant


@pytest.mark.parametrize(
    "name,beta_channel",
    [
        ("button.test_name_ota_update", False),
        ("button.test_name_ota_update_beta", True),
    ],
)
async def test_block_button(
    hass: HomeAssistant, name: str, beta_channel: bool, coap_wrapper
):
    """Test block device OTA button."""
    assert coap_wrapper

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(coap_wrapper.entry, BUTTON_DOMAIN)
    )
    await hass.async_block_till_done()

    state = hass.states.get(name)
    assert state
    assert state.state == STATE_UNKNOWN

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: name},
        blocking=True,
    )
    await hass.async_block_till_done()
    coap_wrapper.device.trigger_ota_update.assert_called_once_with(beta=beta_channel)


@pytest.mark.parametrize(
    "name,beta_channel",
    [
        ("button.test_name_ota_update", False),
        ("button.test_name_ota_update_beta", True),
    ],
)
async def test_rpc_button(
    hass: HomeAssistant, name: str, beta_channel: bool, rpc_wrapper
):
    """Test rpc device OTA button."""
    assert rpc_wrapper

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(rpc_wrapper.entry, BUTTON_DOMAIN)
    )
    await hass.async_block_till_done()

    state = hass.states.get(name)
    assert state
    assert state.state == STATE_UNKNOWN

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: name},
        blocking=True,
    )
    await hass.async_block_till_done()
    rpc_wrapper.device.trigger_ota_update.assert_called_once_with(beta=beta_channel)
