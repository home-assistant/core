"""
This component provides basic support for the Philips Hue system.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/hue/
"""
import ipaddress
import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_FILENAME, CONF_HOST
from homeassistant.helpers import (
    aiohttp_client, config_validation as cv, device_registry as dr)

from .const import DOMAIN, API_NUPNP
from .bridge import HueBridge
# Loading the config flow file will register the flow
from .config_flow import configured_hosts

REQUIREMENTS = ['aiohue==1.5.0']

_LOGGER = logging.getLogger(__name__)

CONF_BRIDGES = "bridges"

CONF_ALLOW_UNREACHABLE = 'allow_unreachable'
DEFAULT_ALLOW_UNREACHABLE = False

PHUE_CONFIG_FILE = 'phue.conf'

CONF_ALLOW_HUE_GROUPS = "allow_hue_groups"
DEFAULT_ALLOW_HUE_GROUPS = True

BRIDGE_CONFIG_SCHEMA = vol.Schema({
    # Validate as IP address and then convert back to a string.
    vol.Required(CONF_HOST): vol.All(ipaddress.ip_address, cv.string),
    # This is for legacy reasons and is only used for importing auth.
    vol.Optional(CONF_FILENAME, default=PHUE_CONFIG_FILE): cv.string,
    vol.Optional(CONF_ALLOW_UNREACHABLE,
                 default=DEFAULT_ALLOW_UNREACHABLE): cv.boolean,
    vol.Optional(CONF_ALLOW_HUE_GROUPS,
                 default=DEFAULT_ALLOW_HUE_GROUPS): cv.boolean,
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_BRIDGES):
            vol.All(cv.ensure_list, [BRIDGE_CONFIG_SCHEMA]),
    }),
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Set up the Hue platform."""
    conf = config.get(DOMAIN)
    if conf is None:
        conf = {}

    hass.data[DOMAIN] = {}
    configured = configured_hosts(hass)

    # User has configured bridges
    if CONF_BRIDGES in conf:
        bridges = conf[CONF_BRIDGES]

    # Component is part of config but no bridges specified, discover.
    elif DOMAIN in config:
        # discover from nupnp
        websession = aiohttp_client.async_get_clientsession(hass)

        async with websession.get(API_NUPNP) as req:
            hosts = await req.json()

        bridges = []
        for entry in hosts:
            # Filter out already configured hosts
            if entry['internalipaddress'] in configured:
                continue

            # Run through config schema to populate defaults
            bridges.append(BRIDGE_CONFIG_SCHEMA({
                CONF_HOST: entry['internalipaddress'],
                # Careful with using entry['id'] for other reasons. The
                # value is in lowercase but is returned uppercase from hub.
                CONF_FILENAME: '.hue_{}.conf'.format(entry['id']),
            }))
    else:
        # Component not specified in config, we're loaded via discovery
        bridges = []

    if not bridges:
        return True

    for bridge_conf in bridges:
        host = bridge_conf[CONF_HOST]

        # Store config in hass.data so the config entry can find it
        hass.data[DOMAIN][host] = bridge_conf

        # If configured, the bridge will be set up during config entry phase
        if host in configured:
            continue

        # No existing config entry found, try importing it or trigger link
        # config flow if no existing auth. Because we're inside the setup of
        # this component we'll have to use hass.async_add_job to avoid a
        # deadlock: creating a config entry will set up the component but the
        # setup would block till the entry is created!
        hass.async_add_job(hass.config_entries.flow.async_init(
            DOMAIN, context={'source': config_entries.SOURCE_IMPORT},
            data={
                'host': bridge_conf[CONF_HOST],
                'path': bridge_conf[CONF_FILENAME],
            }
        ))

    return True


async def async_setup_entry(hass, entry):
    """Set up a bridge from a config entry."""
    host = entry.data['host']
    config = hass.data[DOMAIN].get(host)

    if config is None:
        allow_unreachable = DEFAULT_ALLOW_UNREACHABLE
        allow_groups = DEFAULT_ALLOW_HUE_GROUPS
    else:
        allow_unreachable = config[CONF_ALLOW_UNREACHABLE]
        allow_groups = config[CONF_ALLOW_HUE_GROUPS]

    bridge = HueBridge(hass, entry, allow_unreachable, allow_groups)
    hass.data[DOMAIN][host] = bridge

    if not await bridge.async_setup():
        return False

    config = bridge.api.config
    device_registry = await dr.async_get_registry(hass)
    device_registry.async_get_or_create(
        config_entry=entry.entry_id,
        connections={
            (dr.CONNECTION_NETWORK_MAC, config.mac)
        },
        identifiers={
            (DOMAIN, config.bridgeid)
        },
        manufacturer='Signify',
        name=config.name,
        # Not yet exposed as properties in aiohue
        model=config.raw['modelid'],
        sw_version=config.raw['swversion'],
    )

    return True


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    bridge = hass.data[DOMAIN].pop(entry.data['host'])
    return await bridge.async_reset()
