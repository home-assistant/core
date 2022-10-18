"""Tests for Shelly update platform."""
from homeassistant.components.shelly.const import DOMAIN
from homeassistant.components.update import DOMAIN as UPDATE_DOMAIN, SERVICE_INSTALL
from homeassistant.const import ATTR_ENTITY_ID, STATE_ON, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_component import async_update_entity
from homeassistant.helpers.entity_registry import async_get

from . import init_integration


async def test_block_update(hass: HomeAssistant, mock_block_device, monkeypatch):
    """Test block device update entity."""
    entity_registry = async_get(hass)
    entity_registry.async_get_or_create(
        UPDATE_DOMAIN,
        DOMAIN,
        "test-mac-fwupdate",
        suggested_object_id="test_name_firmware_update",
        disabled_by=None,
    )
    await init_integration(hass, 1)

    assert hass.states.get("update.test_name_firmware_update").state == STATE_ON

    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: "update.test_name_firmware_update"},
        blocking=True,
    )
    assert mock_block_device.trigger_ota_update.call_count == 1

    monkeypatch.setitem(mock_block_device.status["update"], "old_version", None)
    monkeypatch.setitem(mock_block_device.status["update"], "new_version", None)

    # update entity
    await async_update_entity(hass, "update.test_name_firmware_update")

    assert hass.states.get("update.test_name_firmware_update").state == STATE_UNKNOWN


async def test_rpc_update(hass: HomeAssistant, mock_rpc_device, monkeypatch):
    """Test rpc device update entity."""
    entity_registry = async_get(hass)
    entity_registry.async_get_or_create(
        UPDATE_DOMAIN,
        DOMAIN,
        "shelly-sys-fwupdate",
        suggested_object_id="test_name_firmware_update",
        disabled_by=None,
    )
    await init_integration(hass, 2)

    assert hass.states.get("update.test_name_firmware_update").state == STATE_ON

    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: "update.test_name_firmware_update"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert mock_rpc_device.trigger_ota_update.call_count == 1

    monkeypatch.setitem(mock_rpc_device.status["sys"], "available_updates", {})
    monkeypatch.setattr(mock_rpc_device, "shelly", None)

    # update entity
    await async_update_entity(hass, "update.test_name_firmware_update")

    assert hass.states.get("update.test_name_firmware_update").state == STATE_UNKNOWN
