"""Support for Supla devices."""
from datetime import timedelta
import logging
from typing import Optional

from pysupla import SuplaAPI
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_ACCESS_TOKEN
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

from .const import CONF_CHANNELS, CONF_SERVER, CONF_SERVERS, DOMAIN

_LOGGER = logging.getLogger(__name__)


SUPLA_FUNCTION_HA_CMP_MAP = {
    "CONTROLLINGTHEROLLERSHUTTER": "cover",
    "CONTROLLINGTHEGATE": "cover",
    "LIGHTSWITCH": "switch",
    "POWERSWITCH": "switch",
}
SUPLA_FUNCTION_NONE = "NONE"
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
    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][CONF_SERVER] = {}
    hass.data[DOMAIN][CONF_CHANNELS] = {}

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
    """Set up SUPLA as config entry."""
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}
    hass.async_create_task(async_discover_devices(hass, config_entry))
    return True


async def async_unload_entry(hass, config_entry):
    """Unload a config entry."""
    # TODO await hass.config_entries.async_forward_entry_unload(config_entry, "xxx")
    return True


async def async_discover_devices(hass, config_entry):
    """
    Run periodically to discover new devices.

    Currently it's only run at startup.
    """

    server = SuplaAPI(
        config_entry.data[CONF_SERVER], config_entry.data[CONF_ACCESS_TOKEN]
    )

    hass.data[DOMAIN][CONF_SERVER][config_entry.entry_id] = server
    component_configs = {}

    for channel in server.get_channels(include=["iodevice"]):
        channel_function = channel["function"]["name"]
        component_name = SUPLA_FUNCTION_HA_CMP_MAP.get(channel_function)

        if component_name is None:
            _LOGGER.info(
                "Unsupported function: %s, channel id: %s",
                channel_function,
                channel["id"],
            )
            continue

        component_configs.setdefault(component_name, []).append(channel)

    # Load discovered devices
    for component_name, channel in component_configs.items():
        hass.data[DOMAIN][CONF_CHANNELS][component_name] = channel
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, component_name)
        )


class SuplaChannel(Entity):
    """Base class of a Supla Channel (an equivalent of HA's Entity)."""

    def __init__(self, channel_data, supla_server, scan_interval_in_sec):
        """Channel data -- raw channel information from PySupla."""
        self.channel_data = channel_data
        self.supla_server = supla_server
        self.update = Throttle(timedelta(seconds=scan_interval_in_sec))(self._update)

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.channel_data["iodevice"]["gUIDString"])},
            "name": "SUPLA",
            "manufacturer": "ZAMEL Sp. z oo",
            "model": self.channel_data["function"]["name"],
            "sw_version": self.channel_data["iodevice"]["softwareVersion"],
            "via_device": None,
        }

    @property
    def server(self):
        """Return PySupla's server component associated with entity."""
        return self.supla_server

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
        if "iodevice" in self.channel_data:
            if "comment" in self.channel_data["iodevice"]:
                return self.channel_data["iodevice"]["comment"]
            if "name" in self.channel_data["iodevice"]:
                return "supla: " + self.channel_data["iodevice"]["name"]
        if "caption" in self.channel_data:
            return self.channel_data["caption"]
        if "type" in self.channel_data:
            return "supla: " + self.channel_data["type"]["caption"]
        return ""

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        if self.channel_data is None:
            return False
        state = self.channel_data.get("state")
        if state is None:
            return False
        return state.get("connected")

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

    def _update(self):
        """Call to update state."""
        _LOGGER.debug("SUPLA _update ")
        self.channel_data = self.server.get_channel(
            self.channel_data["id"], include=["connected", "state"]
        )
