"""Support for the myLeviton decora_wifi component."""

from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_ENTITY_ID,
    CONF_HOST,
    CONF_ID,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.entity_platform import EntityPlatform

from .common import CommFailed, DecoraWifiPlatform, LoginFailed, LoginMismatch
from .const import CONF_OPTIONS, CONF_TITLE, DEFAULT_SCAN_INTERVAL, DOMAIN, PLATFORMS

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


async def async_setup(hass: HomeAssistant, config):
    """Set up the Decora Wifi component."""
    hass.data.setdefault(
        DOMAIN, EntityComponent(_LOGGER, DOMAIN, hass, timedelta(DEFAULT_SCAN_INTERVAL))
    )

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

    # Verify the Unique ID matches, then add the entity to hass
    if session.unique_id == conf_data[CONF_ID]:
        await component.async_add_entities([session], False)
    else:
        _LOGGER.error(
            "Userid mismatch with config entry. If trying to setup a different account, delete this entry and make a new one."
        )
        raise LoginMismatch("Userid mismatch with config entry.")
    conf_data[CONF_ENTITY_ID] = session.entity_id
    hass.config_entries.async_update_entry(
        entry, title=f"{CONF_TITLE} - {CONF_USERNAME}", data=conf_data
    )

    activeplatforms = session.active_platforms
    # Forward the config entry to each platform which has devices to set up.
    hass.config_entries.async_setup_platforms(entry, activeplatforms)
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
