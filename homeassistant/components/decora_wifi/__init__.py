"""Support for the myLeviton decora_wifi component."""

import logging

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .common import CommFailed, DecoraWifiPlatform, LoginFailed
from .const import DOMAIN, PLATFORMS

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config):
    """Set up the Decora Wifi component."""
    hass.data.setdefault(DOMAIN, {})

    if DOMAIN not in config:
        return True

    # Trigger import config flow
    conf = config[DOMAIN]

    if not hass.config_entries.async_entries(DOMAIN):
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_IMPORT},
                data={
                    CONF_USERNAME: conf[CONF_USERNAME],
                    CONF_PASSWORD: conf[CONF_PASSWORD],
                },
            )
        )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Decora Wifi from a config entry."""

    conf_data = dict(entry.data)
    email = conf_data[CONF_USERNAME]
    password = conf_data[CONF_PASSWORD]

    try:
        session = await DecoraWifiPlatform.async_setup_decora_wifi(
            hass,
            email,
            password,
        )
    except LoginFailed as exc:
        raise ConfigEntryAuthFailed from exc
    except CommFailed as exc:
        raise ConfigEntryNotReady from exc
    hass.data[DOMAIN][entry.entry_id] = session

    # Forward the config entry to each platform which has devices to set up.
    active_platforms = hass.data[DOMAIN][entry.entry_id].active_platforms
    hass.config_entries.async_setup_platforms(entry, active_platforms)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    session: DecoraWifiPlatform = hass.data[DOMAIN].get(entry.entry_id, None)
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        if session:
            try:
                # Attempt to log out.
                await hass.async_add_executor_job(session.teardown)
            except CommFailed:
                _LOGGER.debug(
                    "Communication with myLeviton failed while attempting to logout"
                )
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
