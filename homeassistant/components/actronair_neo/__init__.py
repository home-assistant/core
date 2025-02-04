"""The Actron Air Neo integration."""

from actron_neo_api import ActronNeoAPI

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_TOKEN, CONF_DEVICE_ID
from homeassistant.core import HomeAssistant

from .const import PLATFORM
from .coordinator import ActronNeoDataUpdateCoordinator
from .models import ActronAirNeoData

type ActronConfigEntry = ConfigEntry[ActronAirNeoData]


async def async_setup_entry(hass: HomeAssistant, entry: ActronConfigEntry) -> bool:
    """Set up Actron Air Neo integration from a config entry."""

    pairing_token = entry.data[CONF_API_TOKEN]
    serial_number = entry.data[CONF_DEVICE_ID]

    api = ActronNeoAPI(pairing_token=pairing_token)
    await api.refresh_token()

    # Initialize the data coordinator
    coordinator = ActronNeoDataUpdateCoordinator(hass, api, serial_number)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = ActronAirNeoData(
        pairing_token, coordinator, api, serial_number
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORM)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORM)
