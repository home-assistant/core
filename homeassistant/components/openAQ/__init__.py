"""The OpenAQ Integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import API_KEY_ID, DOMAIN, LOCATION_ID, PLATFORMS
from .coordinator import OpenAQDataCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up this integration from config entry."""

    api_key = entry.data[API_KEY_ID]
    location_id = entry.data[LOCATION_ID]

    coordinator = OpenAQDataCoordinator(hass, api_key, location_id)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, str(coordinator.client.get_device().id))},
        name=coordinator.client.get_device().locality,
        model=coordinator.client.get_device().owner.name,
    )

    return True
