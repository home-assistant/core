"""The init tests for the nexia platform."""


from homeassistant.components.nexia.const import DOMAIN
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.entity_registry import EntityRegistry
from homeassistant.setup import async_setup_component

from .util import async_init_integration


async def remove_device(ws_client, device_id, config_entry_id):
    """Remove config entry from a device."""
    await ws_client.send_json(
        {
            "id": 5,
            "type": "config/device_registry/remove_config_entry",
            "config_entry_id": config_entry_id,
            "device_id": device_id,
        }
    )
    response = await ws_client.receive_json()
    return response["success"]


async def test_device_remove_devices(hass, hass_ws_client):
    """Test we can only remove a device that no longer exists."""
    await async_setup_component(hass, "config", {})
    config_entry = await async_init_integration(hass)
    entry_id = config_entry.entry_id
    device_registry = dr.async_get(hass)

    registry: EntityRegistry = er.async_get(hass)
    entity = registry.entities["sensor.nick_office_temperature"]

    live_zone_device_entry = device_registry.async_get(entity.device_id)
    assert (
        await remove_device(
            await hass_ws_client(hass), live_zone_device_entry.id, entry_id
        )
        is False
    )

    entity = registry.entities["sensor.master_suite_relative_humidity"]
    live_thermostat_device_entry = device_registry.async_get(entity.device_id)
    assert (
        await remove_device(
            await hass_ws_client(hass), live_thermostat_device_entry.id, entry_id
        )
        is False
    )

    dead_device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "unused")},
    )
    assert (
        await remove_device(await hass_ws_client(hass), dead_device_entry.id, entry_id)
        is True
    )
