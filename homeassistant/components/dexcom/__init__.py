"""The Dexcom integration."""
import asyncio
from datetime import timedelta
import logging

from pydexcom import AccountError, Dexcom, SessionError
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, PLATFORMS

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=180)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Dexcom component."""
    conf = config.get(DOMAIN)
    hass.data.setdefault(DOMAIN, {})

    if not conf:
        return True

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={
                CONF_USERNAME: conf.get(CONF_USERNAME),
                CONF_PASSWORD: conf.get(CONF_PASSWORD),
            },
        )
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Dexcom from a config entry."""
    try:
        dexcom = await hass.async_add_executor_job(
            Dexcom, entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD]
        )
    except (AccountError, SessionError):
        raise ConfigEntryNotReady

    async def async_update_data():
        try:
            return await hass.async_add_executor_job(dexcom.get_current_glucose_reading)
        except SessionError:
            await hass.async_add_executor_job(dexcom.create_session())
            return await hass.async_add_executor_job(dexcom.get_current_glucose_reading)

    hass.data[DOMAIN][entry.entry_id] = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=DOMAIN,
        update_method=async_update_data,
        update_interval=SCAN_INTERVAL,
    )

    await hass.data[DOMAIN][entry.entry_id].async_refresh()

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
