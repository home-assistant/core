"""
Roon (www.roonlabs.com) component.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/roon/
"""
import logging
from homeassistant import config_entries
from homeassistant.helpers import device_registry as dr
from .server import RoonServer
from homeassistant.const import CONF_HOST
from .const import (DOMAIN, DATA_CONFIGS, CONFIG_SCHEMA, CONF_CUSTOM_PLAY_ACTION)

# We need an import from .config_flow, without it .config_flow is never loaded.
from .config_flow import FlowHandler, configured_hosts

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass, config):
    """Set up the Roon platform."""
    conf = config.get(DOMAIN)
    if conf is None:
        conf = {}

    hass.data[DOMAIN] = {}
    hass.data[DATA_CONFIGS] = {}
    configured_servers = configured_hosts(hass)

    if CONF_HOST not in conf:
        # User has component configured but with no configured host
        if not configured_servers:
            # trigger config flow (can be removed once roon is added as official component to hass)
            hass.async_create_task(hass.config_entries.flow.async_init(
                DOMAIN, context={'source': config_entries.SOURCE_IMPORT}
            ))
        return True
    # setup component with config from configfile
    host = conf[CONF_HOST]
    # Store config in hass.data so the config entry can find it
    hass.data[DATA_CONFIGS][host] = conf
    # If configured, the server will be set up during config entry phase
    if host in configured_servers:
        return True
    # No existing config entry found, try importing it or trigger link
    # config flow if no existing auth. Because we're inside the setup of
    # this component we'll have to use hass.async_add_job to avoid a
    # deadlock: creating a config entry will set up the component but the
    # setup would block till the entry is created!
    hass.async_create_task(hass.config_entries.flow.async_init(
        DOMAIN, context={'source': config_entries.SOURCE_IMPORT},
        data=conf
    ))
    return True


async def async_setup_entry(hass, entry):
    """Set up a roonserver from a config entry."""
    host = entry.data[CONF_HOST]
    config = hass.data[DATA_CONFIGS].get(host)
    if config is None:
        custom_play_action = None
    else:
        custom_play_action = config[CONF_CUSTOM_PLAY_ACTION]
    roonserver = RoonServer(hass, entry, custom_play_action)

    if not await roonserver.async_setup():
        return False

    hass.data[DOMAIN][host] = roonserver
    device_registry = await dr.async_get_registry(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={
            (CONF_HOST, host)
        },
        identifiers={
            (DOMAIN, host)
        },
        manufacturer='Roonlabs',
        name=host,
        model="",
        sw_version="",
    )
    return True


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    roonserver = hass.data[DOMAIN].pop(entry.data[CONF_HOST])
    return await roonserver.async_reset()
