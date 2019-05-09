"""Support for the Philips Hue system."""
import ipaddress
import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_FILENAME, CONF_HOST
from homeassistant.helpers import (
    config_validation as cv, device_registry as dr)

from .const import DOMAIN
from .bridge import HueBridge
# Loading the config flow file will register the flow
from .config_flow import configured_hosts

_LOGGER = logging.getLogger(__name__)

CONF_BRIDGES = "bridges"

CONF_ALLOW_UNREACHABLE = 'allow_unreachable'
DEFAULT_ALLOW_UNREACHABLE = False

DATA_CONFIGS = 'hue_configs'

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
    hass.data[DATA_CONFIGS] = {}
    configured = configured_hosts(hass)

    # User has configured bridges
    if CONF_BRIDGES not in conf:
        return True

    bridges = conf[CONF_BRIDGES]

    for bridge_conf in bridges:
        host = bridge_conf[CONF_HOST]

        # Store config in hass.data so the config entry can find it
        hass.data[DATA_CONFIGS][host] = bridge_conf

        # If configured, the bridge will be set up during config entry phase
        if host in configured:
            continue

        # No existing config entry found, try importing it or trigger link
        # config flow if no existing auth. Because we're inside the setup of
        # this component we'll have to use hass.async_add_job to avoid a
        # deadlock: creating a config entry will set up the component but the
        # setup would block till the entry is created!
        hass.async_create_task(hass.config_entries.flow.async_init(
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
    config = hass.data[DATA_CONFIGS].get(host)

    if config is None:
        allow_unreachable = DEFAULT_ALLOW_UNREACHABLE
        allow_groups = DEFAULT_ALLOW_HUE_GROUPS
    else:
        allow_unreachable = config[CONF_ALLOW_UNREACHABLE]
        allow_groups = config[CONF_ALLOW_HUE_GROUPS]

    bridge = HueBridge(hass, entry, allow_unreachable, allow_groups)

    if not await bridge.async_setup():
        return False

    hass.data[DOMAIN][host] = bridge
    config = bridge.api.config
    device_registry = await dr.async_get_registry(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={
            (dr.CONNECTION_NETWORK_MAC, config.mac)
        },
        identifiers={
            (DOMAIN, config.bridgeid)
        },
        manufacturer='Signify',
        name=config.name,
        model=config.modelid,
        sw_version=config.swversion,
    )

    if config.swupdate2_bridge_state == "readytoinstall":
        err = (
            "Please check for software updates of the bridge "
            "in the Philips Hue App."
        )
        _LOGGER.warning(err)

    return True


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    bridge = hass.data[DOMAIN].pop(entry.data['host'])
    return await bridge.async_reset()
