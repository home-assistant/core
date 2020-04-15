"""Helper functions for Acmeda Pulse."""
from homeassistant.helpers.device_registry import async_get_registry as get_dev_reg
from homeassistant.helpers.entity_registry import async_get_registry as get_ent_reg

from .const import DOMAIN, LOGGER


async def update_entities(
    hass, entity_class, config_entry, current, async_add_entities
):
    """Add any new entities, remove any old ones."""
    hub = hass.data[DOMAIN][config_entry.entry_id]
    LOGGER.debug("Looking for new %s on: %s", entity_class.__name__, hub.host)

    api = hub.api.rollers

    new_items = []
    for unique_id, roller in api.items():
        if unique_id not in current:
            LOGGER.debug("New %s %s", entity_class.__name__, unique_id)
            new_item = entity_class(hass, roller)
            current[unique_id] = new_item
            new_items.append(new_item)

    async_add_entities(new_items)

    LOGGER.debug("Looking for removed %s on: %s", entity_class.__name__, hub.host)

    removed_items = []
    for unique_id, element in current.items():
        if unique_id not in api:
            LOGGER.debug("Removing %s %s", entity_class.__name__, unique_id)
            removed_items.append(element)

    for entity in removed_items:
        # Device is removed from Pulse, so we remove it from Home Assistant

        await entity.async_remove()
        ent_registry = await get_ent_reg(hass)
        if entity.entity_id in ent_registry.entities:
            ent_registry.async_remove(entity.entity_id)
        dev_registry = await get_dev_reg(hass)
        device = dev_registry.async_get_device(
            identifiers={(DOMAIN, entity.device_id)}, connections=set()
        )
        if device is not None:
            dev_registry.async_update_device(
                device.id, remove_config_entry_id=config_entry.entry_id
            )
        del current[entity.unique_id]


async def update_devices(hass, config_entry, api):
    """Tell hass that device info has been updated."""
    dev_registry = await get_dev_reg(hass)

    for api_item in api.values():
        # Update Device name
        device = dev_registry.async_get_device(
            identifiers={(DOMAIN, api_item.id)}, connections=set()
        )
        if device is not None:
            dev_registry.async_update_device(
                device.id, name=api_item.name,
            )
