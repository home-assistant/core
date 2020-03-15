"""Support for Nexia / Trane XL Thermostats."""
from datetime import timedelta
import logging

from nexia.home import NexiaHome
from requests.exceptions import ConnectTimeout, HTTPError
import voluptuous as vol

from homeassistant.const import (
    CONF_ID,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

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
ATTR_HUMIDIFY_SUPPORTED = "humidify_supported"
ATTR_DEHUMIDIFY_SUPPORTED = "dehumidify_supported"
ATTR_HUMIDIFY_SETPOINT = "humidify_setpoint"
ATTR_DEHUMIDIFY_SETPOINT = "dehumidify_setpoint"

UPDATE_COORDINATOR = "udpate_coordinator"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Optional(CONF_ID): cv.positive_int,
                vol.Optional(CONF_SCAN_INTERVAL): cv.positive_int,
            }
        ),
    },
    extra=vol.ALLOW_EXTRA,
)

DEFAULT_UPDATE_RATE = 120


def setup(hass, config):
    """Configure the base Nexia device for Home Assistant."""

    conf = config[DOMAIN]

    username = conf[CONF_USERNAME]
    password = conf[CONF_PASSWORD]
    house_id = conf.get(CONF_ID)

    scan_interval = timedelta(seconds=conf.get(CONF_SCAN_INTERVAL, DEFAULT_UPDATE_RATE))

    nexia_home = None

    try:
        nexia_home = NexiaHome(
            username=username, password=password, house_id=house_id, auto_login=True
        )
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

    async def _async_update_data():
        """Fetch data from API endpoint."""
        return await hass.async_add_job(nexia_home.update)

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="Nexia update",
        update_method=_async_update_data,
        update_interval=scan_interval,
    )

    hass.data[DATA_NEXIA] = {
        NEXIA_DEVICE: nexia_home,
        NEXIA_SCAN_INTERVAL: scan_interval,
        UPDATE_COORDINATOR: coordinator,
    }

    return True


def is_percent(value):
    """If the value is a valid percentage."""
    return isinstance(value, int) and 0 <= value <= 100
