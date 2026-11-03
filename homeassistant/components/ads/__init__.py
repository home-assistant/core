"""Support for Automation Device Specification (ADS)."""

import logging

import probatio
import pyads

from homeassistant.const import (
    CONF_DEVICE,
    CONF_IP_ADDRESS,
    CONF_PORT,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DATA_ADS, DOMAIN
from .hub import AdsHub
from .services import setup_services

_LOGGER = logging.getLogger(__name__)


CONFIG_SCHEMA = probatio.Schema(
    {
        DOMAIN: probatio.Schema(
            {
                probatio.Required(CONF_DEVICE): cv.string,
                probatio.Required(CONF_PORT): probatio.Port(),
                probatio.Optional(CONF_IP_ADDRESS): cv.string,
            }
        )
    },
    extra=probatio.ALLOW_EXTRA,
)


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the ADS component."""
    setup_services(hass)

    conf = config[DOMAIN]

    net_id = conf[CONF_DEVICE]
    ip_address = conf.get(CONF_IP_ADDRESS)
    port = conf[CONF_PORT]

    client = pyads.Connection(net_id, port, ip_address)

    try:
        ads = AdsHub(client)
    except pyads.ADSError:
        _LOGGER.error(
            "Could not connect to ADS host (netid=%s, ip=%s, port=%s)",
            net_id,
            ip_address,
            port,
        )
        return False

    hass.data[DATA_ADS] = ads
    hass.bus.listen(EVENT_HOMEASSISTANT_STOP, ads.shutdown)

    return True
