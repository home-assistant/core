"""Support for IHC devices."""
import logging

from ihcsdk.ihccontroller import IHCController
import voluptuous as vol

from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME
from homeassistant.core import HomeAssistant
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
    IHC_CONTROLLER_INDEX,
    IHC_PLATFORMS,
)
from .service_functions import setup_service_functions

_LOGGER = logging.getLogger(__name__)


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


def ihc_setup(
    hass: HomeAssistant,
    config: ConfigType,
    controller_conf: ConfigType,
    controller_index: int,
):
    """Set up the IHC integration."""
    url = controller_conf[CONF_URL]
    username = controller_conf[CONF_USERNAME]
    password = controller_conf[CONF_PASSWORD]

    ihc_controller = IHCController(url, username, password)
    if not ihc_controller.authenticate():
        _LOGGER.error("Unable to authenticate on IHC controller")
        return False
    controller_id: str = ihc_controller.client.get_system_info()["serial_number"]
    # Store controller configuration
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][controller_id] = {
        IHC_CONTROLLER: ihc_controller,
        CONF_INFO: controller_conf[CONF_INFO],
        IHC_CONTROLLER_INDEX: controller_index,
    }
    if controller_conf[CONF_AUTOSETUP] and not autosetup_ihc_products(
        hass, config, ihc_controller, controller_id
    ):
        return False
    get_manual_configuration(hass, config, controller_conf, controller_id)
    # We only want to register the service functions once for the first controller
    if controller_index == 0:
        setup_service_functions(hass)
    return True


def get_manual_configuration(
    hass: HomeAssistant,
    config: ConfigType,
    controller_conf,
    controller_id: str,
) -> None:
    """Get manual configuration for IHC devices."""
    for platform in IHC_PLATFORMS:
        discovery_info = {}
        if platform in controller_conf:
            platform_setup = controller_conf.get(platform)
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
