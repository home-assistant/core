"""The Dexcom integration."""

from datetime import timedelta
import logging

from pydexcom import AccountError, Dexcom, GlucoseReading, SessionError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_SERVER, DOMAIN, PLATFORMS, SERVER_OUS

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=180)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Dexcom from a config entry."""
    try:
        dexcom = await hass.async_add_executor_job(
            Dexcom,
            entry.data[CONF_USERNAME],
            entry.data[CONF_PASSWORD],
            entry.data[CONF_SERVER] == SERVER_OUS,
        )
    except AccountError:
        return False
    except SessionError as error:
        raise ConfigEntryNotReady from error

    async def async_update_data():
        try:
            return await hass.async_add_executor_job(dexcom.get_current_glucose_reading)
        except SessionError as error:
            raise UpdateFailed(error) from error

    coordinator = DataUpdateCoordinator[GlucoseReading](
        hass,
        _LOGGER,
        config_entry=entry,
        name=DOMAIN,
        update_method=async_update_data,
        update_interval=SCAN_INTERVAL,
    )
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
