"""The System Nexa 2 integration."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN, MANUFACTURER, PLATFORMS
from .coordinator import SystemNexa2ConfigEntry, SystemNexa2DataUpdateCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: SystemNexa2ConfigEntry) -> bool:
    """Set up from a config entry."""
    coordinator = SystemNexa2DataUpdateCoordinator(hass, config_entry=entry)
    await coordinator.async_setup()

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, coordinator.data.unique_id)},
        manufacturer=MANUFACTURER,
        name=coordinator.data.info_data.name,
        model=coordinator.data.info_data.model,
        sw_version=coordinator.data.info_data.sw_version,
        hw_version=str(coordinator.data.info_data.hw_version),
    )
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: SystemNexa2ConfigEntry
) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await entry.runtime_data.device.disconnect()
    return unload_ok
