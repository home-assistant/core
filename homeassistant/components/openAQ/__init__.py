"""The OpenAQ Integration."""

from homeassistant.components.openAQ.cordinator import OpenAQDataCoordinator
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import API_KEY_ID, LOCATION_ID, DOMAIN, PLATFORMS

# async def async_setup(hass: HomeAssistant, config: Config) -> bool:
#     """Read configuration from yaml."""

#     pass


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up this integration from config entry."""

    api_key = entry.data[API_KEY_ID]
    location_id = entry.data[LOCATION_ID]

    coordinator = OpenAQDataCoordinator(hass,api_key,location_id)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    device_registry = dr.async_get(hass)

    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "test")},
        name="test",  # needs to be the same as in sensor.py Station name
        model="Unknown",  # Add later from api
    )

    return True


# async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
#     """Handle removal of an entry."""
#     return True
