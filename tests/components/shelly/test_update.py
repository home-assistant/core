"""Tests for Shelly update platform."""
from homeassistant.components.update import DOMAIN as UPDATE_DOMAIN
from homeassistant.components.update.const import SERVICE_INSTALL
from homeassistant.components.shelly.const import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import async_get


async def test_block_update(hass: HomeAssistant, coap_wrapper):
    """Test block device update entity."""
    assert coap_wrapper

    entity_registry = async_get(hass)
    entity_registry.async_get_or_create(
        UPDATE_DOMAIN,
        DOMAIN,
        "test_name_update",
        suggested_object_id="test_name_update",
        disabled_by=None,
    )
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(coap_wrapper.entry, UPDATE_DOMAIN)
    )
    await hass.async_block_till_done()

    # update entity
    state = hass.states.get("update.test_name_update")

    assert state
    assert state.state == STATE_UNKNOWN

    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: "update.test_name_update"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert coap_wrapper.device.trigger_ota_update.call_count == 1


async def test_rpc_update(hass: HomeAssistant, rpc_wrapper):
    """Test rpc device update entity."""
    assert rpc_wrapper

    entity_registry = async_get(hass)
    entity_registry.async_get_or_create(
        UPDATE_DOMAIN,
        DOMAIN,
        "test_name_update",
        suggested_object_id="test_name_update",
        disabled_by=None,
    )

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(rpc_wrapper.entry, UPDATE_DOMAIN)
    )
    await hass.async_block_till_done()

    # update entity
    state = hass.states.get("update.test_name_reboot")

    assert state
    assert state.state == STATE_UNKNOWN

    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: "update.test_name_reboot"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert rpc_wrapper.device.trigger_ota_update.call_count == 1
