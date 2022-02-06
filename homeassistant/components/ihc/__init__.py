"""Support for IHC devices."""
import logging

from ihcsdk.ihccontroller import IHCController
import voluptuous as vol

from homeassistant.components.binary_sensor import DEVICE_CLASSES_SCHEMA
from homeassistant.const import (
    CONF_ID,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_TYPE,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_URL,
    CONF_USERNAME,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .auto_setup import autosetup_ihc_products
from .const import (
    CONF_AUTOSETUP,
    CONF_BINARY_SENSOR,
    CONF_DIMMABLE,
    CONF_INFO,
    CONF_INVERTING,
    CONF_LIGHT,
    CONF_NOTE,
    CONF_OFF_ID,
    CONF_ON_ID,
    CONF_POSITION,
    CONF_SENSOR,
    CONF_SWITCH,
    DOMAIN,
    IHC_CONTROLLER,
    IHC_PLATFORMS,
)
from .service_functions import setup_service_functions

_LOGGER = logging.getLogger(__name__)

IHC_INFO = "info"


def validate_name(config):
    """Validate the device name."""
    if CONF_NAME in config:
        return config
    ihcid = config[CONF_ID]
    name = f"ihc_{ihcid}"
    config[CONF_NAME] = name
    return config


DEVICE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ID): cv.positive_int,
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_NOTE): cv.string,
        vol.Optional(CONF_POSITION): cv.string,
    }
)


SWITCH_SCHEMA = DEVICE_SCHEMA.extend(
    {
        vol.Optional(CONF_OFF_ID, default=0): cv.positive_int,
        vol.Optional(CONF_ON_ID, default=0): cv.positive_int,
    }
)

BINARY_SENSOR_SCHEMA = DEVICE_SCHEMA.extend(
    {
        vol.Optional(CONF_INVERTING, default=False): cv.boolean,
        vol.Optional(CONF_TYPE): DEVICE_CLASSES_SCHEMA,
    }
)

LIGHT_SCHEMA = DEVICE_SCHEMA.extend(
    {
        vol.Optional(CONF_DIMMABLE, default=False): cv.boolean,
        vol.Optional(CONF_OFF_ID, default=0): cv.positive_int,
        vol.Optional(CONF_ON_ID, default=0): cv.positive_int,
    }
)

SENSOR_SCHEMA = DEVICE_SCHEMA.extend(
    {vol.Optional(CONF_UNIT_OF_MEASUREMENT, default=TEMP_CELSIUS): cv.string}
)

IHC_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_URL): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Optional(CONF_AUTOSETUP, default=True): cv.boolean,
        vol.Optional(CONF_BINARY_SENSOR, default=[]): vol.All(
            cv.ensure_list, [vol.All(BINARY_SENSOR_SCHEMA, validate_name)]
        ),
        vol.Optional(CONF_INFO, default=True): cv.boolean,
        vol.Optional(CONF_LIGHT, default=[]): vol.All(
            cv.ensure_list, [vol.All(LIGHT_SCHEMA, validate_name)]
        ),
        vol.Optional(CONF_SENSOR, default=[]): vol.All(
            cv.ensure_list, [vol.All(SENSOR_SCHEMA, validate_name)]
        ),
        vol.Optional(CONF_SWITCH, default=[]): vol.All(
            cv.ensure_list, [vol.All(SWITCH_SCHEMA, validate_name)]
        ),
    }
)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Schema(vol.All(cv.ensure_list, [IHC_SCHEMA]))}, extra=vol.ALLOW_EXTRA
)


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the IHC integration."""
    conf = config[DOMAIN]
    for index, controller_conf in enumerate(conf):
        if not ihc_setup(hass, config, controller_conf, index):
            return False

    return True


def ihc_setup(hass, config, conf, controller_id):
    """Set up the IHC integration."""
    url = conf[CONF_URL]
    username = conf[CONF_USERNAME]
    password = conf[CONF_PASSWORD]

    ihc_controller = IHCController(url, username, password)
    if not ihc_controller.authenticate():
        _LOGGER.error("Unable to authenticate on IHC controller")
        return False

    if conf[CONF_AUTOSETUP] and not autosetup_ihc_products(
        hass, config, ihc_controller, controller_id
    ):
        return False
    # Manual configuration
    get_manual_configuration(hass, config, conf, ihc_controller, controller_id)
    # Store controller configuration
    ihc_key = f"ihc{controller_id}"
    hass.data[ihc_key] = {IHC_CONTROLLER: ihc_controller, IHC_INFO: conf[CONF_INFO]}
    # We only want to register the service functions once for the first controller
    if controller_id == 0:
        setup_service_functions(hass)
    return True


def get_manual_configuration(hass, config, conf, ihc_controller, controller_id):
    """Get manual configuration for IHC devices."""
    for platform in IHC_PLATFORMS:
        discovery_info = {}
        if platform in conf:
            platform_setup = conf.get(platform)
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
