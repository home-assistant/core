"""The totalconnect component."""

from total_connect_client.client import TotalConnectClient
from total_connect_client.exceptions import AuthenticationError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
import homeassistant.helpers.config_validation as cv

from .const import AUTO_BYPASS, CONF_USERCODES, DOMAIN
from .coordinator import TotalConnectDataUpdateCoordinator

PLATFORMS = [Platform.ALARM_CONTROL_PANEL, Platform.BINARY_SENSOR, Platform.BUTTON]

CONFIG_SCHEMA = cv.removed(DOMAIN, raise_if_present=False)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up upon config entry in user interface."""
    conf = entry.data
    username = conf[CONF_USERNAME]
    password = conf[CONF_PASSWORD]
    bypass = entry.options.get(AUTO_BYPASS, False)

    if CONF_USERCODES not in conf:
        # should only happen for those who used UI before we added usercodes
        raise ConfigEntryAuthFailed("No usercodes in TotalConnect configuration")

    temp_codes = conf[CONF_USERCODES]
    usercodes = {int(code): temp_codes[code] for code in temp_codes}

    try:
        client = await hass.async_add_executor_job(
            TotalConnectClient, username, password, usercodes, bypass
        )
    except AuthenticationError as exception:
        raise ConfigEntryAuthFailed(
            "TotalConnect authentication failed during setup"
        ) from exception

    coordinator = TotalConnectDataUpdateCoordinator(hass, client)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update listener."""
    bypass = entry.options.get(AUTO_BYPASS, False)
    client = hass.data[DOMAIN][entry.entry_id].client
    for location_id in client.locations:
        client.locations[location_id].auto_bypass_low_battery = bypass
