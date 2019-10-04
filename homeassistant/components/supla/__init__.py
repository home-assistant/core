"""Support for Supla devices."""
import logging
from typing import Optional

import voluptuous as vol

from homeassistant.const import CONF_ACCESS_TOKEN
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import load_platform
from homeassistant.helpers.entity import Entity
from homeassistant.config_entries import SOURCE_IMPORT
from pysupla import SuplaAPI

REQUIREMENTS = ["pysupla==0.0.3"]

_LOGGER = logging.getLogger(__name__)
DOMAIN = "supla"

CONF_SERVER = "server"
CONF_SERVERS = "servers"

SUPLA_FUNCTION_HA_CMP_MAP = {
    "CONTROLLINGTHEROLLERSHUTTER": "cover",
    "LIGHTSWITCH": "switch",
    "POWERSWITCH": "switch",
}
SUPLA_CHANNELS = "supla_channels"
SUPLA_SERVERS = "supla_servers"

SERVER_CONFIG = vol.Schema(
    {vol.Required(CONF_SERVER): cv.string, vol.Required(CONF_ACCESS_TOKEN): cv.string}
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {vol.Required(CONF_SERVERS): vol.All(cv.ensure_list, [SERVER_CONFIG])}
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Set up the Supla component."""
    hass.data[SUPLA_SERVERS] = {}
    hass.data[SUPLA_CHANNELS] = {}

    if not hass.config_entries.async_entries(DOMAIN) and DOMAIN in config:
        server_confs = config[DOMAIN][CONF_SERVERS]

        for server_conf in server_confs:
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN, context={"source": SOURCE_IMPORT}, data=server_conf
                )
            )

    return True


async def async_setup_entry(hass, config_entry):
    """Set up supla as config entry."""
    _LOGGER.info("supla async_setup_entry")
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    server_address = config_entry.data[CONF_SERVER]
    supla_server = SuplaAPI(server_address, config_entry.data[CONF_ACCESS_TOKEN])
    hass.data[SUPLA_SERVERS][config_entry.data[CONF_SERVER]] = supla_server

    hass.async_create_task(async_discover_devices(hass, config_entry))

    return True


async def async_discover_devices(hass, config_entry):
    """
    Run periodically to discover new devices.

    Currently it's only run at startup.
    """
    component_configs = {}

    for server_name, server in hass.data[SUPLA_SERVERS].items():

        for channel in server.get_channels(include=["iodevice"]):
            channel_function = channel["function"]["name"]
            component_name = SUPLA_FUNCTION_HA_CMP_MAP.get(channel_function)

            if component_name is None:
                _LOGGER.warning(
                    "Unsupported function: %s, channel id: %s",
                    channel_function,
                    channel["id"],
                )
                continue

            channel["server_name"] = server_name
            component_configs.setdefault(component_name, []).append(channel)

    # Load discovered devices
    for component_name, channel in component_configs.items():
        load_platform(hass, component_name, "supla", channel, config_entry.data)


class SuplaChannel(Entity):
    """Base class of a Supla Channel (an equivalent of HA's Entity)."""

    def __init__(self, channel_data):
        """Channel data -- raw channel information from PySupla."""
        self.server_name = channel_data["server_name"]
        self.channel_data = channel_data

    @property
    def server(self):
        """Return PySupla's server component associated with entity."""
        return self.hass.data[SUPLA_SERVERS][self.server_name]

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return "supla-{}-{}".format(
            self.channel_data["iodevice"]["gUIDString"].lower(),
            self.channel_data["channelNumber"],
        )

    @property
    def name(self) -> Optional[str]:
        """Return the name of the device."""
        return self.channel_data["caption"]

    def action(self, action, **add_pars):
        """
        Run server action.

        Actions are currently hardcoded in components.
        Supla's API enables autodiscovery
        """
        _LOGGER.debug(
            "Executing action %s on channel %d, params: %s",
            action,
            self.channel_data["id"],
            add_pars,
        )
        self.server.execute_action(self.channel_data["id"], action, **add_pars)

    def update(self):
        """Call to update state."""
        self.channel_data = self.server.get_channel(
            self.channel_data["id"], include=["connected", "state"]
        )
