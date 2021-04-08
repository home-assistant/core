"""Helper functions for Acmeda Pulse."""
from homeassistant.core import callback
from homeassistant.helpers.device_registry import async_get_registry as get_dev_reg

from .const import DOMAIN, LOGGER


@callback
def async_add_acmeda_entities(
    hass, entity_class, config_entry, current, async_add_entities
):
    """Add any new entities."""
    hub = hass.data[DOMAIN][config_entry.entry_id]
    LOGGER.debug("Looking for new %s on: %s", entity_class.__name__, hub.host)

    api = hub.api.rollers

    new_items = []
    for unique_id, roller in api.items():
        if unique_id not in current:
            LOGGER.debug("New %s %s", entity_class.__name__, unique_id)
            new_item = entity_class(roller)
            current.add(unique_id)
            new_items.append(new_item)

    async_add_entities(new_items)


async def update_devices(hass, config_entry, api):
    """Tell hass that device info has been updated."""
    dev_registry = await get_dev_reg(hass)

    for api_item in api.values():
        # Update Device name
        device = dev_registry.async_get_device(identifiers={(DOMAIN, api_item.id)})
        if device is not None:
            dev_registry.async_update_device(
                device.id,
                name=api_item.name,
            )
