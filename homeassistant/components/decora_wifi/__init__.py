"""Support for the myLeviton decora_wifi component."""

import logging

import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
import homeassistant.helpers.config_validation as cv

from .common import CommFailed, DecoraWifiPlatform, LoginFailed
from .const import CONF_OPTIONS, DEFAULT_SCAN_INTERVAL, DOMAIN, PLATFORMS

_LOGGER = logging.getLogger(__name__)

DECORAWIFI_HOST_SCHEMA = vol.Schema({vol.Required(CONF_HOST): cv.string})

CONFIG_SCHEMA = vol.Schema(
    vol.All(
        cv.deprecated(DOMAIN),
        {
            DOMAIN: vol.Schema(
                {
                    vol.Required(CONF_USERNAME): cv.string,
                    vol.Required(CONF_PASSWORD): cv.string,
                    vol.Optional(CONF_SCAN_INTERVAL, default=120): cv.positive_int,
                },
            )
        },
    ),
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
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

    # Set scan interval, or grab a sane default.
    conf_data[CONF_OPTIONS] = {
        CONF_SCAN_INTERVAL: dict(entry.options).get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )
    }

    # If a session is already setup, don't start a new one.
    session: DecoraWifiPlatform = hass.data[DOMAIN].get(entry.entry_id, None)
    if not session:
        # Re-login
        try:
            # Attempt to log in.
            session = await DecoraWifiPlatform.async_setup_decora_wifi(
                hass,
                email,
                password,
            )
        except LoginFailed as exc:
            _LOGGER.error("Login failed")
            raise ConfigEntryAuthFailed from exc
        except CommFailed as exc:
            _LOGGER.error("Communication with myLeviton failed")
            raise ConfigEntryNotReady from exc
        hass.data[DOMAIN].update({entry.entry_id: session})

    if session:
        active_platforms = session.active_platforms
        # Forward the config entry to each platform which has devices to set up.
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
                _LOGGER.warning(
                    "Communication with myLeviton failed while attempting to logout"
                )
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
