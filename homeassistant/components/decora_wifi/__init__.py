"""Support for the myLeviton decora_wifi component."""

import logging

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_SCAN_INTERVAL, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .common import CommFailed, DecoraWifiPlatform, LoginFailed, LoginMismatch
from .const import CONF_OPTIONS, CONF_TITLE, DEFAULT_SCAN_INTERVAL, DOMAIN, PLATFORMS

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

    component: EntityComponent = hass.data[DOMAIN]

    # Set a sane default scan interval.
    conf_data[CONF_OPTIONS] = {
        CONF_SCAN_INTERVAL: dict(entry.options).get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )
    }

    # Login and store session in hass.data
    try:
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
    hass.data[DOMAIN][entry.entry_id] = session

    # Forward the config entry to each platform which has devices to set up.
    active_platforms = session.active_platforms
    hass.config_entries.async_setup_platforms(entry, active_platforms)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    conf_data = dict(entry.data)

    # Unload the entity associated with this config entry
    component: EntityComponent = hass.data[DOMAIN]
    entity = component.get_entity(conf_data[CONF_ENTITY_ID])
    if entity:
        platform: EntityPlatform = entity.platform
        await platform.async_remove_entity(conf_data[CONF_ENTITY_ID])

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
