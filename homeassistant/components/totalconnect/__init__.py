"""The totalconnect component."""

from total_connect_client.client import TotalConnectClient
from total_connect_client.exceptions import AuthenticationError

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed

from .const import AUTO_BYPASS, CONF_USERCODES
from .coordinator import TotalConnectConfigEntry, TotalConnectDataUpdateCoordinator

PLATFORMS = [Platform.ALARM_CONTROL_PANEL, Platform.BINARY_SENSOR, Platform.BUTTON]


async def async_setup_entry(
    hass: HomeAssistant, entry: TotalConnectConfigEntry
) -> bool:
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

    coordinator = TotalConnectDataUpdateCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(update_listener))

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: TotalConnectConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def update_listener(hass: HomeAssistant, entry: TotalConnectConfigEntry) -> None:
    """Update listener."""
    bypass = entry.options.get(AUTO_BYPASS, False)
    client = entry.runtime_data.client
    for location_id in client.locations:
        client.locations[location_id].auto_bypass_low_battery = bypass
