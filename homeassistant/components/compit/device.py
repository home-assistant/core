"""Device registry management for Compit integration."""

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN, MANUFACTURER_NAME
from .coordinator import CompitConfigEntry


def setup_devices(
    hass: HomeAssistant,
    entry: CompitConfigEntry,
) -> None:
    """Set up devices in the device registry."""
    coordinator = entry.runtime_data
    device_registry = dr.async_get(hass)

    @callback
    def register_devices() -> None:
        """Register all devices in the device registry."""
        for device_id, device in coordinator.data.items():
            device_registry.async_get_or_create(
                config_entry_id=entry.entry_id,
                identifiers={(DOMAIN, str(device_id))},
                name=device.definition.name,
                manufacturer=MANUFACTURER_NAME,
                model=device.definition.name,
            )

    register_devices()
    entry.async_on_unload(coordinator.async_add_listener(register_devices))
