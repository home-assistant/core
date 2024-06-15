"""The Derivative integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SOURCE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Derivative from a config entry."""

    await async_remove_stale_device_links(
        hass, entry.entry_id, entry.options[CONF_SOURCE]
    )

    await hass.config_entries.async_forward_entry_setups(entry, (Platform.SENSOR,))
    entry.async_on_unload(entry.add_update_listener(config_entry_update_listener))
    return True


async def config_entry_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update listener, called when the config entry options are changed."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, (Platform.SENSOR,))


async def async_remove_stale_device_links(
    hass: HomeAssistant, entry_id: str, entity_id: str
) -> None:
    """Remove device link for entry, the source device may have changed."""

    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)

    # Resolve source entity device
    current_device_id = None
    if ((source_entity := entity_registry.async_get(entity_id)) is not None) and (
        source_entity.device_id is not None
    ):
        current_device_id = source_entity.device_id

    devices_in_entry = device_registry.devices.get_devices_for_config_entry_id(entry_id)

    # Removes all devices from the config entry that are not the same as the current device
    for device in devices_in_entry:
        if device.id == current_device_id:
            continue
        device_registry.async_update_device(device.id, remove_config_entry_id=entry_id)
