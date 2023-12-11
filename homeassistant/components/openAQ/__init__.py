"""The OpenAQ Integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import API_KEY_ID, DOMAIN, LOCATION_ID, PLATFORMS
from .coordinator import OpenAQDataCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up this integration from config entry."""

    api_key = entry.data[API_KEY_ID]  # Get api key from config_flow
    location_id = entry.data[LOCATION_ID]  # Get location_id from config_flow

    coordinator = OpenAQDataCoordinator(hass, api_key, location_id)

    await coordinator.async_config_entry_first_refresh()  # Make a first refresh on all entities

    hass.data.setdefault(DOMAIN, {})[
        entry.entry_id
    ] = coordinator  # Register coordinator to the hass object

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(  # Create a new station device
        config_entry_id=entry.entry_id,
        identifiers={
            (DOMAIN, str(coordinator.client.get_device().id))
        },  # This is used in order to access the device
        name=coordinator.client.get_device().locality,  # We give the device the same name as the station the user has set up in config_flow
        model=coordinator.client.get_device().owner.name,  # We give the device the same manufactorer as the user has set up in config_flow
    )

    return True
