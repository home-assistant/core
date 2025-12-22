"""Device registry management for Compit integration."""

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN, MANUFACTURER_NAME
from .coordinator import CompitConfigEntry


def setup_devices(
    hass: HomeAssistant,
    entry: CompitConfigEntry,
) -> None:
    """Register all devices from the coordinator in the device registry."""
    coordinator = entry.runtime_data
    device_registry = dr.async_get(hass)

    @callback
    def register_devices() -> None:
        """Register all devices and remove stale devices from the device registry."""
        current_device_ids = {str(device_id) for device_id in coordinator.data}

        # Register or update devices
        for device_id, device in coordinator.data.items():
            device_registry.async_get_or_create(
                config_entry_id=entry.entry_id,
                identifiers={(DOMAIN, str(device_id))},
                name=device.definition.name,
                manufacturer=MANUFACTURER_NAME,
                model=device.definition.name,
            )

        # Remove stale devices that are no longer in the API response
        for device_entry in dr.async_entries_for_config_entry(
            device_registry, entry.entry_id
        ):
            # Check if this device's identifier is still in the current API data
            for identifier in device_entry.identifiers:
                if identifier[0] == DOMAIN and identifier[1] not in current_device_ids:
                    device_registry.async_update_device(
                        device_entry.id,
                        remove_config_entry_id=entry.entry_id,
                    )
                    break

    register_devices()
    entry.async_on_unload(coordinator.async_add_listener(register_devices))
