"""Provide migration tools for the Tradfri integration."""
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.device_registry as dr

from .const import DOMAIN


@callback
def migrate_device_identifier(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Migrate device identifier to new format."""
    device_registry = dr.async_get(hass)
    device_entries = dr.async_entries_for_config_entry(
        device_registry, config_entry.entry_id
    )

    for device_entry in device_entries:
        device_identifiers = set(device_entry.identifiers)

        for identifier in device_entry.identifiers:
            if identifier[0] == DOMAIN and isinstance(
                identifier[1], int  # type: ignore[unreachable]
            ):
                device_identifiers.remove(identifier)  # type: ignore[unreachable]
                # Copy pytradfri device id to string.
                device_identifiers.add((DOMAIN, str(identifier[1])))
                break

        if device_identifiers != device_entry.identifiers:
            device_registry.async_update_device(
                device_entry.id, new_identifiers=device_identifiers
            )
