"""Support for Supla devices."""
import logging
from typing import Optional

import voluptuous as vol

from homeassistant.const import CONF_ACCESS_TOKEN
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import load_platform
from homeassistant.helpers.entity import Entity
from homeassistant.config_entries import SOURCE_IMPORT
from .const import DOMAIN, CONF_SERVER, CONF_SERVERS

from pysupla import SuplaAPI


_LOGGER = logging.getLogger(__name__)


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


async def async_setup_entry(hass, config_entry):
    """Set up supla as config entry."""
    _LOGGER.info("supla async_setup_entry")
    hass.async_create_task(async_discover_devices(hass, config_entry))

    return True


async def async_setup(hass, base_config):
    """Set up the Supla component."""
    if DOMAIN not in base_config:
        return True

    server_confs = base_config[DOMAIN][CONF_SERVERS]

    hass.data[SUPLA_SERVERS] = {}
    hass.data[SUPLA_CHANNELS] = {}

    for server_conf in server_confs:

        server_address = server_conf[CONF_SERVER]

        server = SuplaAPI(server_address, server_conf[CONF_ACCESS_TOKEN])

        # Test connection
        try:
            srv_info = server.get_server_info()
            if srv_info.get("authenticated"):
                # hass.data[SUPLA_SERVERS][server_conf[CONF_SERVER]] = server
                hass.async_create_task(
                    hass.config_entries.flow.async_init(
                        DOMAIN,
                        context={"source": SOURCE_IMPORT},
                        data={
                            CONF_SERVER: server_conf[CONF_SERVER],
                            CONF_ACCESS_TOKEN: server_conf[CONF_ACCESS_TOKEN],
                        },
                    )
                )
            else:
                _LOGGER.error(
                    "Server: %s not configured. API call returned: %s",
                    server_address,
                    srv_info,
                )
                return False
        except OSError:
            _LOGGER.exception(
                "Server: %s not configured. Error on Supla API access: ", server_address
            )
            return False

    return True


async def async_discover_devices(hass, config_entry):
    """
    Run periodically to discover new devices.

    Currently it's only run at startup.
    """
    component_configs = {}
    server_address = config_entry.data[CONF_SERVER]
    server = SuplaAPI(server_address, config_entry.data[CONF_ACCESS_TOKEN])
    _LOGGER.info("supla async_discover_devices from server " + str(server))
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

        channel["server_name"] = server_address
        component_configs.setdefault(component_name, []).append(channel)

    # Load discovered devices
    for component_name, channel in component_configs.items():
        load_platform(hass, component_name, "supla", channel, config_entry)


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
