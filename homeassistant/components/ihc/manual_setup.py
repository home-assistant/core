"""Handle manual setup of ihc resources as entities in Home Assistant."""

import logging

import probatio

from homeassistant.components.binary_sensor import DEVICE_CLASSES_SCHEMA
from homeassistant.const import (
    CONF_ID,
    CONF_NAME,
    CONF_NOTE,
    CONF_PASSWORD,
    CONF_TYPE,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_URL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, discovery
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_AUTOSETUP,
    CONF_BINARY_SENSOR,
    CONF_DIMMABLE,
    CONF_INFO,
    CONF_INVERTING,
    CONF_LIGHT,
    CONF_OFF_ID,
    CONF_ON_ID,
    CONF_POSITION,
    CONF_SENSOR,
    CONF_SWITCH,
    DOMAIN,
    IHC_PLATFORMS,
)

_LOGGER = logging.getLogger(__name__)


def validate_name(config):
    """Validate the device name."""
    if CONF_NAME in config:
        return config
    ihcid = config[CONF_ID]
    name = f"ihc_{ihcid}"
    config[CONF_NAME] = name
    return config


DEVICE_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_ID): cv.positive_int,
        probatio.Optional(CONF_NAME): cv.string,
        probatio.Optional(CONF_NOTE): cv.string,
        probatio.Optional(CONF_POSITION): cv.string,
    }
)

SWITCH_SCHEMA = DEVICE_SCHEMA.extend(
    {
        probatio.Optional(CONF_OFF_ID, default=0): cv.positive_int,
        probatio.Optional(CONF_ON_ID, default=0): cv.positive_int,
    }
)

BINARY_SENSOR_SCHEMA = DEVICE_SCHEMA.extend(
    {
        probatio.Optional(CONF_INVERTING, default=False): cv.boolean,
        probatio.Optional(CONF_TYPE): DEVICE_CLASSES_SCHEMA,
    }
)

LIGHT_SCHEMA = DEVICE_SCHEMA.extend(
    {
        probatio.Optional(CONF_DIMMABLE, default=False): cv.boolean,
        probatio.Optional(CONF_OFF_ID, default=0): cv.positive_int,
        probatio.Optional(CONF_ON_ID, default=0): cv.positive_int,
    }
)

SENSOR_SCHEMA = DEVICE_SCHEMA.extend(
    {probatio.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string}
)

IHC_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_PASSWORD): cv.string,
        probatio.Required(CONF_URL): cv.string,
        probatio.Required(CONF_USERNAME): cv.string,
        probatio.Optional(CONF_AUTOSETUP, default=True): cv.boolean,
        probatio.Optional(CONF_BINARY_SENSOR, default=[]): probatio.All(
            cv.ensure_list, [probatio.All(BINARY_SENSOR_SCHEMA, validate_name)]
        ),
        probatio.Optional(CONF_INFO, default=True): cv.boolean,
        probatio.Optional(CONF_LIGHT, default=[]): probatio.All(
            cv.ensure_list, [probatio.All(LIGHT_SCHEMA, validate_name)]
        ),
        probatio.Optional(CONF_SENSOR, default=[]): probatio.All(
            cv.ensure_list, [probatio.All(SENSOR_SCHEMA, validate_name)]
        ),
        probatio.Optional(CONF_SWITCH, default=[]): probatio.All(
            cv.ensure_list, [probatio.All(SWITCH_SCHEMA, validate_name)]
        ),
    }
)


def get_manual_configuration(
    hass: HomeAssistant,
    config: ConfigType,
    controller_conf: ConfigType,
    controller_id: str,
) -> None:
    """Get manual configuration for IHC devices."""
    for platform in IHC_PLATFORMS:
        discovery_info = {}
        if platform in controller_conf:
            platform_setup = controller_conf.get(platform, {})
            for sensor_cfg in platform_setup:
                name = sensor_cfg[CONF_NAME]
                device = {
                    "ihc_id": sensor_cfg[CONF_ID],
                    "ctrl_id": controller_id,
                    "product": {
                        "name": name,
                        "note": sensor_cfg.get(CONF_NOTE) or "",
                        "position": sensor_cfg.get(CONF_POSITION) or "",
                    },
                    "product_cfg": {
                        "type": sensor_cfg.get(CONF_TYPE),
                        "inverting": sensor_cfg.get(CONF_INVERTING),
                        "off_id": sensor_cfg.get(CONF_OFF_ID),
                        "on_id": sensor_cfg.get(CONF_ON_ID),
                        "dimmable": sensor_cfg.get(CONF_DIMMABLE),
                        "unit_of_measurement": sensor_cfg.get(CONF_UNIT_OF_MEASUREMENT),
                    },
                }
                discovery_info[name] = device
        if discovery_info:
            discovery.load_platform(hass, platform, DOMAIN, discovery_info, config)
