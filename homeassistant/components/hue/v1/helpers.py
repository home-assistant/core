"""Helper functions for Philips Hue."""

from homeassistant.helpers import device_registry as dr, entity_registry as er

from ..const import DOMAIN


async def remove_devices(bridge, api_ids, current):
    """Get items that are removed from api."""
    removed_items = []

    for item_id in current:
        if item_id in api_ids:
            continue

        # Device is removed from Hue, so we remove it from Home Assistant
        entity = current[item_id]
        removed_items.append(item_id)
        await entity.async_remove(force_remove=True)
        ent_registry = er.async_get(bridge.hass)
        if entity.entity_id in ent_registry.entities:
            ent_registry.async_remove(entity.entity_id)
        dev_registry = dr.async_get(bridge.hass)
        device = dev_registry.async_get_device(identifiers={(DOMAIN, entity.device_id)})
        if device is not None:
            dev_registry.async_update_device(
                device.id, remove_config_entry_id=bridge.config_entry.entry_id
            )

    for item_id in removed_items:
        del current[item_id]
