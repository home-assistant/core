"""Support to control a Salda Smarty XP/XV ventilation unit."""

from datetime import timedelta
import ipaddress
import logging

from pysmarty2 import Smarty
import voluptuous as vol

from homeassistant.const import CONF_HOST, CONF_NAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import dispatcher_send
from homeassistant.helpers.event import track_time_interval
from homeassistant.helpers.typing import ConfigType

DOMAIN = "smarty"
DATA_SMARTY = "smarty"
SMARTY_NAME = "Smarty"

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_HOST): vol.All(ipaddress.ip_address, cv.string),
                vol.Optional(CONF_NAME, default=SMARTY_NAME): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

RPM = "rpm"
SIGNAL_UPDATE_SMARTY = "smarty_update"


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the smarty environment."""

    conf = config[DOMAIN]

    host = conf[CONF_HOST]
    name = conf[CONF_NAME]

    _LOGGER.debug("Name: %s, host: %s", name, host)

    smarty = Smarty(host=host)

    hass.data[DOMAIN] = {"api": smarty, "name": name}

    # Initial update
    smarty.update()

    # Load platforms
    discovery.load_platform(hass, Platform.FAN, DOMAIN, {}, config)
    discovery.load_platform(hass, Platform.SENSOR, DOMAIN, {}, config)
    discovery.load_platform(hass, Platform.BINARY_SENSOR, DOMAIN, {}, config)

    def poll_device_update(event_time):
        """Update Smarty device."""
        _LOGGER.debug("Updating Smarty device")
        if smarty.update():
            _LOGGER.debug("Update success")
            dispatcher_send(hass, SIGNAL_UPDATE_SMARTY)
        else:
            _LOGGER.debug("Update failed")

    track_time_interval(hass, poll_device_update, timedelta(seconds=30))

    return True
