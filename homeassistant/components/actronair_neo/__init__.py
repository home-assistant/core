"""The Actron Air Neo integration."""

from actron_neo_api import ActronNeoAPI

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .const import DOMAIN, PLATFORMS
from .coordinator import ActronNeoDataUpdateCoordinator
from .device import ACUnit
from .models import ActronAirNeoData


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Actron Air Neo integration from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    pairing_token = entry.data.get("pairing_token")
    serial_number = entry.data.get("serial_number")

    if not pairing_token or not serial_number:
        raise ConfigEntryAuthFailed("Invalid authentication")

    api = ActronNeoAPI(pairing_token=pairing_token)
    await api.refresh_token()

    # Initialize the data coordinator
    coordinator = ActronNeoDataUpdateCoordinator(hass, api, serial_number)
    await coordinator.async_config_entry_first_refresh()

    # Ensure coordinator data is not None
    if coordinator.data is None:
        raise ConfigEntryNotReady("Unable to retrieve data from the API")

    # Fetch system details and set up ACUnit
    system = await api.get_ac_systems()
    ac_unit = ACUnit(serial_number, system, coordinator.data)

    entry.runtime_data = ActronAirNeoData(coordinator, api, ac_unit, serial_number)

    # Store objects in hass.data
    hass.data[DOMAIN][entry.entry_id] = {
        "api": api,
        "coordinator": coordinator,
        "ac_unit": ac_unit,
        "serial_number": serial_number,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the Actron Air Neo integration."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = True
    for platform in PLATFORMS:
        unload_ok = unload_ok and await hass.config_entries.async_forward_entry_unload(
            entry, platform
        )

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
