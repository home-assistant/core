"""The Ridder HortiMaX Pro (HortOS) integration."""

from aiohortos import HortosClient

from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, MANUFACTURER
from .coordinator import HortimaxConfigEntry, HortimaxCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: HortimaxConfigEntry) -> bool:
    """Set up Ridder HortiMaX Pro from a config entry."""
    client = HortosClient(
        entry.data[CONF_API_KEY], session=async_get_clientsession(hass)
    )
    coordinator = HortimaxCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    # Registered up front so the sensor platform's source devices can point at
    # them through via_device.
    device_registry = dr.async_get(hass)
    for device in coordinator.devices:
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, device.name)},
            manufacturer=MANUFACTURER,
            name=device.label or device.name,
            model="HortiMaX Pro",
            serial_number=device.name,
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: HortimaxConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
