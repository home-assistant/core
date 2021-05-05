"""Support for IHC devices."""
import logging
import os.path

from defusedxml import ElementTree
from ihcsdk.ihccontroller import IHCController
import voluptuous as vol

from homeassistant.components.binary_sensor import DEVICE_CLASSES_SCHEMA
from homeassistant.config import load_yaml_config_file
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

from .const import (
    ATTR_CONTROLLER_ID,
    ATTR_IHC_ID,
    ATTR_VALUE,
    CONF_AUTOSETUP,
    CONF_BINARY_SENSOR,
    CONF_DIMMABLE,
    CONF_INFO,
    CONF_INVERTING,
    CONF_LIGHT,
    CONF_NODE,
    CONF_NOTE,
    CONF_OFF_ID,
    CONF_ON_ID,
    CONF_POSITION,
    CONF_SENSOR,
    CONF_SWITCH,
    CONF_XPATH,
    SERVICE_PULSE,
    SERVICE_SET_RUNTIME_VALUE_BOOL,
    SERVICE_SET_RUNTIME_VALUE_FLOAT,
    SERVICE_SET_RUNTIME_VALUE_INT,
)
from .util import async_pulse

_LOGGER = logging.getLogger(__name__)

AUTO_SETUP_YAML = "ihc_auto_setup.yaml"

DOMAIN = "ihc"

IHC_CONTROLLER = "controller"
IHC_INFO = "info"
PLATFORMS = ("binary_sensor", "light", "sensor", "switch")


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


AUTO_SETUP_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_BINARY_SENSOR, default=[]): vol.All(
            cv.ensure_list,
            [
                vol.All(
                    {
                        vol.Required(CONF_NODE): cv.string,
                        vol.Required(CONF_XPATH): cv.string,
                        vol.Optional(CONF_INVERTING, default=False): cv.boolean,
                        vol.Optional(CONF_TYPE): cv.string,
                    }
                )
            ],
        ),
        vol.Optional(CONF_LIGHT, default=[]): vol.All(
            cv.ensure_list,
            [
                vol.All(
                    {
                        vol.Required(CONF_NODE): cv.string,
                        vol.Required(CONF_XPATH): cv.string,
                        vol.Optional(CONF_DIMMABLE, default=False): cv.boolean,
                    }
                )
            ],
        ),
        vol.Optional(CONF_SENSOR, default=[]): vol.All(
            cv.ensure_list,
            [
                vol.All(
                    {
                        vol.Required(CONF_NODE): cv.string,
                        vol.Required(CONF_XPATH): cv.string,
                        vol.Optional(
                            CONF_UNIT_OF_MEASUREMENT, default=TEMP_CELSIUS
                        ): cv.string,
                    }
                )
            ],
        ),
        vol.Optional(CONF_SWITCH, default=[]): vol.All(
            cv.ensure_list,
            [
                vol.All(
                    {
                        vol.Required(CONF_NODE): cv.string,
                        vol.Required(CONF_XPATH): cv.string,
                    }
                )
            ],
        ),
    }
)

SET_RUNTIME_VALUE_BOOL_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_IHC_ID): cv.positive_int,
        vol.Required(ATTR_VALUE): cv.boolean,
        vol.Optional(ATTR_CONTROLLER_ID, default=0): cv.positive_int,
    }
)

SET_RUNTIME_VALUE_INT_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_IHC_ID): cv.positive_int,
        vol.Required(ATTR_VALUE): vol.Coerce(int),
        vol.Optional(ATTR_CONTROLLER_ID, default=0): cv.positive_int,
    }
)

SET_RUNTIME_VALUE_FLOAT_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_IHC_ID): cv.positive_int,
        vol.Required(ATTR_VALUE): vol.Coerce(float),
        vol.Optional(ATTR_CONTROLLER_ID, default=0): cv.positive_int,
    }
)

PULSE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_IHC_ID): cv.positive_int,
        vol.Optional(ATTR_CONTROLLER_ID, default=0): cv.positive_int,
    }
)


def setup(hass, config):
    """Set up the IHC integration."""
    conf = config.get(DOMAIN)
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
    for platform in PLATFORMS:
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


def autosetup_ihc_products(hass: HomeAssistant, config, ihc_controller, controller_id):
    """Auto setup of IHC products from the IHC project file."""
    project_xml = ihc_controller.get_project()
    if not project_xml:
        _LOGGER.error("Unable to read project from IHC controller")
        return False
    project = ElementTree.fromstring(project_xml)

    # If an auto setup file exist in the configuration it will override
    yaml_path = hass.config.path(AUTO_SETUP_YAML)
    if not os.path.isfile(yaml_path):
        yaml_path = os.path.join(os.path.dirname(__file__), AUTO_SETUP_YAML)
    yaml = load_yaml_config_file(yaml_path)
    try:
        auto_setup_conf = AUTO_SETUP_SCHEMA(yaml)
    except vol.Invalid as exception:
        _LOGGER.error("Invalid IHC auto setup data: %s", exception)
        return False

    groups = project.findall(".//group")
    for platform in PLATFORMS:
        platform_setup = auto_setup_conf[platform]
        discovery_info = get_discovery_info(platform_setup, groups, controller_id)
        if discovery_info:
            discovery.load_platform(hass, platform, DOMAIN, discovery_info, config)

    return True


def get_discovery_info(platform_setup, groups, controller_id):
    """Get discovery info for specified IHC platform."""
    discovery_data = {}
    for group in groups:
        groupname = group.attrib["name"]
        for product_cfg in platform_setup:
            products = group.findall(product_cfg[CONF_XPATH])
            for product in products:
                nodes = product.findall(product_cfg[CONF_NODE])
                for node in nodes:
                    if "setting" in node.attrib and node.attrib["setting"] == "yes":
                        continue
                    ihc_id = int(node.attrib["id"].strip("_"), 0)
                    name = f"{groupname}_{ihc_id}"
                    device = {
                        "ihc_id": ihc_id,
                        "ctrl_id": controller_id,
                        "product": {
                            "name": product.get("name") or "",
                            "note": product.get("note") or "",
                            "position": product.get("position") or "",
                        },
                        "product_cfg": product_cfg,
                    }
                    discovery_data[name] = device
    return discovery_data


def setup_service_functions(hass: HomeAssistant):
    """Set up the IHC service functions."""

    def _get_controller(call):
        controller_id = call.data[ATTR_CONTROLLER_ID]
        ihc_key = f"ihc{controller_id}"
        return hass.data[ihc_key][IHC_CONTROLLER]

    def set_runtime_value_bool(call):
        """Set a IHC runtime bool value service function."""
        ihc_id = call.data[ATTR_IHC_ID]
        value = call.data[ATTR_VALUE]
        ihc_controller = _get_controller(call)
        ihc_controller.set_runtime_value_bool(ihc_id, value)

    def set_runtime_value_int(call):
        """Set a IHC runtime integer value service function."""
        ihc_id = call.data[ATTR_IHC_ID]
        value = call.data[ATTR_VALUE]
        ihc_controller = _get_controller(call)
        ihc_controller.set_runtime_value_int(ihc_id, value)

    def set_runtime_value_float(call):
        """Set a IHC runtime float value service function."""
        ihc_id = call.data[ATTR_IHC_ID]
        value = call.data[ATTR_VALUE]
        ihc_controller = _get_controller(call)
        ihc_controller.set_runtime_value_float(ihc_id, value)

    async def async_pulse_runtime_input(call):
        """Pulse a IHC controller input function."""
        ihc_id = call.data[ATTR_IHC_ID]
        ihc_controller = _get_controller(call)
        await async_pulse(hass, ihc_controller, ihc_id)

    hass.services.register(
        DOMAIN,
        SERVICE_SET_RUNTIME_VALUE_BOOL,
        set_runtime_value_bool,
        schema=SET_RUNTIME_VALUE_BOOL_SCHEMA,
    )
    hass.services.register(
        DOMAIN,
        SERVICE_SET_RUNTIME_VALUE_INT,
        set_runtime_value_int,
        schema=SET_RUNTIME_VALUE_INT_SCHEMA,
    )
    hass.services.register(
        DOMAIN,
        SERVICE_SET_RUNTIME_VALUE_FLOAT,
        set_runtime_value_float,
        schema=SET_RUNTIME_VALUE_FLOAT_SCHEMA,
    )
    hass.services.register(
        DOMAIN, SERVICE_PULSE, async_pulse_runtime_input, schema=PULSE_SCHEMA
    )
