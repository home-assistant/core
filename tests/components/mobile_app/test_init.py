"""Tests for the mobile app integration."""
from homeassistant.components.mobile_app.const import DATA_DELETED_IDS, DOMAIN
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import CALL_SERVICE

from tests.common import async_mock_service


async def test_unload_unloads(hass, create_registrations, webhook_client):
    """Test we clean up when we unload."""
    # Second config entry is the one without encryption
    config_entry = hass.config_entries.async_entries("mobile_app")[1]
    webhook_id = config_entry.data["webhook_id"]
    calls = async_mock_service(hass, "test", "mobile_app")

    # Test it works
    await webhook_client.post(f"/api/webhook/{webhook_id}", json=CALL_SERVICE)
    assert len(calls) == 1

    await hass.config_entries.async_unload(config_entry.entry_id)

    # Test it no longer works
    await webhook_client.post(f"/api/webhook/{webhook_id}", json=CALL_SERVICE)
    assert len(calls) == 1


async def test_remove_entry(hass, create_registrations):
    """Test we clean up when we remove entry."""
    for config_entry in hass.config_entries.async_entries("mobile_app"):
        await hass.config_entries.async_remove(config_entry.entry_id)
        assert config_entry.data["webhook_id"] in hass.data[DOMAIN][DATA_DELETED_IDS]

    dev_reg = dr.async_get(hass)
    assert len(dev_reg.devices) == 0

    ent_reg = er.async_get(hass)
    assert len(ent_reg.entities) == 0
