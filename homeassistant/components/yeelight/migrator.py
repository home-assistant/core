"""Migrators for Yeelight."""
import logging
from typing import Optional

from homeassistant.config_entries import ConfigEntry, ConfigEntryNotReady
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry, entity_registry

_LOGGER = logging.getLogger(__name__)

DOMAIN = "yeelight"  # TODO: Move all constants to const.py


async def _async_migrate_entity_unique_id(
    hass: HomeAssistant, config_entry: ConfigEntry
):
    """Migrate entity unique IDs to v2 (config entry id)."""

    @callback
    def _async_migrator(entity_entry: entity_registry.RegistryEntry):
        if entity_entry.unique_id.startswith("v2-"):
            return None  # Abort if already v2
        unique_id = f"v2-{config_entry.entry_id}"
        if entity_entry.unique_id.endswith("-ambilight"):
            unique_id += "-ambilight"
        elif entity_entry.unique_id.endswith("-nightlight"):
            unique_id += "-nightlight"
        _LOGGER.debug(
            "Migrate entity unique ID: %s -> %s", entity_entry.unique_id, unique_id
        )
        return {"new_unique_id": unique_id}

    await entity_registry.async_migrate_entries(
        hass, config_entry.entry_id, _async_migrator
    )


async def _async_migrate_device_unique_id(
    hass: HomeAssistant, config_entry: ConfigEntry
):
    """Migrate entity unique IDs to v2 (config entry id)."""
    registry = await device_registry.async_get_registry(hass)
    device_entries = device_registry.async_entries_for_config_entry(
        registry, config_entry.entry_id
    )
    for device_entry in device_entries:
        _, old_id = next(iter(device_entry.identifiers))  # Only one identifier
        if old_id.startswith("v2-"):
            continue  # Abort if already v2
        new_id = f"v2-{config_entry.entry_id}"
        _LOGGER.debug("Migrate device unique ID: %s -> %s", old_id, new_id)
        registry.async_update_device(
            device_entry.id, new_identifiers={(DOMAIN, new_id)}
        )


@callback
def _async_migrate_name(
    hass: HomeAssistant, config_entry: ConfigEntry, capabilities: Optional[dict]
):
    """Move name from options to data."""
    data = {**config_entry.data}
    options = {**config_entry.options}
    data[CONF_NAME] = options.pop(CONF_NAME)
    if not data[CONF_NAME]:
        # Name not set, generate name from capabilities
        if capabilities is None:
            # If the config entry existed and is in old structure
            # we should be able to get capabilities
            raise ConfigEntryNotReady
        model = capabilities["model"]
        unique_id = capabilities["id"]
        data[CONF_NAME] = f"yeelight_{model}_{unique_id}"
    hass.config_entries.async_update_entry(config_entry, data=data, options=options)
