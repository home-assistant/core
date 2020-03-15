"""Support for Nexia / Trane XL Thermostats."""
import logging
from datetime import timedelta

import voluptuous as vol
from requests.exceptions import ConnectTimeout, HTTPError

import homeassistant.helpers.config_validation as cv
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_USERNAME,
    CONF_ID,
    CONF_SCAN_INTERVAL,
)

REQUIREMENTS = [
    "beautifulsoup4==4.6.3",
    "certifi==2018.8.24",
    "chardet==3.0.4",
    "html5lib==1.0.1",
    "idna==2.7",
    "requests==2.19.1",
    "six==1.11.0",
    "urllib3==1.23",
    "webencodings==0.5.1",
]

_LOGGER = logging.getLogger(__name__)

ATTRIBUTION = "Data provided by nexiahome.com"

NOTIFICATION_ID = "nexia_notification"
NOTIFICATION_TITLE = "Nexia Setup"

DATA_NEXIA = "nexia"
NEXIA_DEVICE = "device"
NEXIA_SCAN_INTERVAL = "scan_interval"

DOMAIN = "nexia"
DEFAULT_ENTITY_NAMESPACE = "nexia"

ATTR_FAN = "fan"
ATTR_SYSTEM_MODE = "system_mode"
ATTR_CURRENT_OPERATION = "system_status"
ATTR_MODEL = "model"
ATTR_FIRMWARE = "firmware"
ATTR_THERMOSTAT_NAME = "thermostat_name"
ATTR_HOLD_MODES = "hold_modes"
ATTR_SETPOINT_STATUS = "setpoint_status"
ATTR_ZONE_STATUS = "zone_status"
ATTR_FAN_SPEED = "fan_speed"
ATTR_COMPRESSOR_SPEED = "compressor_speed"
ATTR_OUTDOOR_TEMPERATURE = "outdoor_temperature"
ATTR_THERMOSTAT_ID = "thermostat_id"
ATTR_ZONE_ID = "zone_id"
ATTR_AIRCLEANER_MODE = "aircleaner_mode"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Required(CONF_ID): cv.positive_int,
                vol.Optional(CONF_SCAN_INTERVAL): cv.positive_int,
            }
        ),
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(hass, config):
    """Configure the base Nexia device for Home Assistant."""
    from .nexia_thermostat import NexiaThermostat

    conf = config[DOMAIN]

    username = conf[CONF_USERNAME]
    password = conf[CONF_PASSWORD]
    house_id = conf[CONF_ID]

    scan_interval = timedelta(
        seconds=conf.get(CONF_SCAN_INTERVAL, NexiaThermostat.DEFAULT_UPDATE_RATE)
    )

    try:
        thermostat = NexiaThermostat(
            username=username,
            password=password,
            house_id=house_id,
            update_rate=NexiaThermostat.DISABLE_AUTO_UPDATE,
        )
        hass.data[DATA_NEXIA] = {
            NEXIA_DEVICE: thermostat,
            NEXIA_SCAN_INTERVAL: scan_interval,
        }
    except (ConnectTimeout, HTTPError) as ex:
        _LOGGER.error("Unable to connect to Nexia service: %s", str(ex))
        hass.components.persistent_notification.create(
            "Error: {}<br />"
            "You will need to restart hass after fixing."
            "".format(ex),
            title=NOTIFICATION_TITLE,
            notification_id=NOTIFICATION_ID,
        )
        return False
    return True
