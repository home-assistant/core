"""Tests for Shelly update platform."""
from homeassistant.components.shelly.const import DOMAIN
from homeassistant.components.update import DOMAIN as UPDATE_DOMAIN, SERVICE_INSTALL
from homeassistant.const import ATTR_ENTITY_ID, STATE_ON, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_component import async_update_entity
from homeassistant.helpers.entity_registry import async_get


async def test_block_update(hass: HomeAssistant, coap_wrapper, monkeypatch):
    """Test block device update entity."""
    assert coap_wrapper

    entity_registry = async_get(hass)
    entity_registry.async_get_or_create(
        UPDATE_DOMAIN,
        DOMAIN,
        "test-mac-fwupdate",
        suggested_object_id="test_name_firmware_update",
        disabled_by=None,
    )
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(coap_wrapper.entry, UPDATE_DOMAIN)
    )
    await hass.async_block_till_done()

    # update entity
    await async_update_entity(hass, "update.test_name_firmware_update")
    await hass.async_block_till_done()
    state = hass.states.get("update.test_name_firmware_update")

    assert state
    assert state.state == STATE_ON

    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: "update.test_name_firmware_update"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert coap_wrapper.device.trigger_ota_update.call_count == 1

    monkeypatch.setitem(coap_wrapper.device.status["update"], "old_version", None)
    monkeypatch.setitem(coap_wrapper.device.status["update"], "new_version", None)

    # update entity
    await async_update_entity(hass, "update.test_name_firmware_update")
    await hass.async_block_till_done()
    state = hass.states.get("update.test_name_firmware_update")

    assert state
    assert state.state == STATE_UNKNOWN


async def test_rpc_update(hass: HomeAssistant, rpc_wrapper, monkeypatch):
    """Test rpc device update entity."""
    assert rpc_wrapper

    entity_registry = async_get(hass)
    entity_registry.async_get_or_create(
        UPDATE_DOMAIN,
        DOMAIN,
        "12345678-sys-fwupdate",
        suggested_object_id="test_name_firmware_update",
        disabled_by=None,
    )

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(rpc_wrapper.entry, UPDATE_DOMAIN)
    )
    await hass.async_block_till_done()

    # update entity
    await async_update_entity(hass, "update.test_name_firmware_update")
    await hass.async_block_till_done()
    state = hass.states.get("update.test_name_firmware_update")

    assert state
    assert state.state == STATE_ON

    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: "update.test_name_firmware_update"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert rpc_wrapper.device.trigger_ota_update.call_count == 1

    monkeypatch.setitem(rpc_wrapper.device.status["sys"], "available_updates", {})
    rpc_wrapper.device.shelly = None

    # update entity
    await async_update_entity(hass, "update.test_name_firmware_update")
    await hass.async_block_till_done()
    state = hass.states.get("update.test_name_firmware_update")

    assert state
    assert state.state == STATE_UNKNOWN
