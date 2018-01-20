"""IHC component.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/ihc/
"""
import logging
import os.path
import xml.etree.ElementTree
import voluptuous as vol

from homeassistant.components.ihc.const import (
    ATTR_IHC_ID, ATTR_VALUE, CONF_INFO, CONF_AUTOSETUP,
    CONF_BINARY_SENSOR, CONF_LIGHT, CONF_SENSOR, CONF_SWITCH,
    CONF_XPATH, CONF_NODE, CONF_DIMMABLE, CONF_INVERTING,
    SERVICE_SET_RUNTIME_VALUE_BOOL, SERVICE_SET_RUNTIME_VALUE_INT,
    SERVICE_SET_RUNTIME_VALUE_FLOAT)
from homeassistant.config import load_yaml_config_file
from homeassistant.const import (
    CONF_URL, CONF_USERNAME, CONF_PASSWORD, CONF_ID, CONF_NAME,
    CONF_UNIT_OF_MEASUREMENT, CONF_TYPE, TEMP_CELSIUS)
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import HomeAssistantType

REQUIREMENTS = ['ihcsdk==2.1.1']

DOMAIN = 'ihc'
IHC_DATA = 'ihc'
IHC_CONTROLLER = 'controller'
IHC_INFO = 'info'
AUTO_SETUP_YAML = 'ihc_auto_setup.yaml'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_URL): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_AUTOSETUP, default=True): cv.boolean,
        vol.Optional(CONF_INFO, default=True): cv.boolean
    }),
}, extra=vol.ALLOW_EXTRA)

AUTO_SETUP_SCHEMA = vol.Schema({
    vol.Optional(CONF_BINARY_SENSOR, default=[]):
        vol.All(cv.ensure_list, [
            vol.All({
                vol.Required(CONF_XPATH): cv.string,
                vol.Required(CONF_NODE): cv.string,
                vol.Optional(CONF_TYPE, default=None): cv.string,
                vol.Optional(CONF_INVERTING, default=False): cv.boolean,
            })
        ]),
    vol.Optional(CONF_LIGHT, default=[]):
        vol.All(cv.ensure_list, [
            vol.All({
                vol.Required(CONF_XPATH): cv.string,
                vol.Required(CONF_NODE): cv.string,
                vol.Optional(CONF_DIMMABLE, default=False): cv.boolean,
            })
        ]),
    vol.Optional(CONF_SENSOR, default=[]):
        vol.All(cv.ensure_list, [
            vol.All({
                vol.Required(CONF_XPATH): cv.string,
                vol.Required(CONF_NODE): cv.string,
                vol.Optional(CONF_UNIT_OF_MEASUREMENT,
                             default=TEMP_CELSIUS): cv.string,
            })
        ]),
    vol.Optional(CONF_SWITCH, default=[]):
        vol.All(cv.ensure_list, [
            vol.All({
                vol.Required(CONF_XPATH): cv.string,
                vol.Required(CONF_NODE): cv.string,
            })
        ]),
})

SET_RUNTIME_VALUE_BOOL_SCHEMA = vol.Schema({
    vol.Required(ATTR_IHC_ID): cv.positive_int,
    vol.Required(ATTR_VALUE): cv.boolean
})

SET_RUNTIME_VALUE_INT_SCHEMA = vol.Schema({
    vol.Required(ATTR_IHC_ID): cv.positive_int,
    vol.Required(ATTR_VALUE): int
})

SET_RUNTIME_VALUE_FLOAT_SCHEMA = vol.Schema({
    vol.Required(ATTR_IHC_ID): cv.positive_int,
    vol.Required(ATTR_VALUE): vol.Coerce(float)
})

_LOGGER = logging.getLogger(__name__)

IHC_PLATFORMS = ('binary_sensor', 'light', 'sensor', 'switch')


def setup(hass, config):
    """Setup the IHC component."""
    from ihcsdk.ihccontroller import IHCController
    conf = config[DOMAIN]
    url = conf[CONF_URL]
    username = conf[CONF_USERNAME]
    password = conf[CONF_PASSWORD]
    ihc_controller = IHCController(url, username, password)

    if not ihc_controller.authenticate():
        _LOGGER.error("Unable to authenticate on ihc controller.")
        return False

    if (conf[CONF_AUTOSETUP] and
            not autosetup_ihc_products(hass, config, ihc_controller)):
        return False

    hass.data[IHC_DATA] = {
        IHC_CONTROLLER: ihc_controller,
        IHC_INFO: conf[CONF_INFO]}

    setup_service_functions(hass, ihc_controller)
    return True


def autosetup_ihc_products(hass: HomeAssistantType, config, ihc_controller):
    """Auto setup of IHC products from the ihc project file."""
    project_xml = ihc_controller.get_project()
    if not project_xml:
        _LOGGER.error("Unable to read project from ihc controller.")
        return False
    project = xml.etree.ElementTree.fromstring(project_xml)

    # if an auto setup file exist in the configuration it will override
    yaml_path = hass.config.path(AUTO_SETUP_YAML)
    if not os.path.isfile(yaml_path):
        yaml_path = os.path.join(os.path.dirname(__file__), AUTO_SETUP_YAML)
    yaml = load_yaml_config_file(yaml_path)
    try:
        auto_setup_conf = AUTO_SETUP_SCHEMA(yaml)
    except vol.Invalid as exception:
        _LOGGER.error("Invalid IHC auto setup data: %s", exception)
        return False
    groups = project.findall('.//group')
    for component in IHC_PLATFORMS:
        component_setup = auto_setup_conf[component]
        discovery_info = get_discovery_info(component_setup, groups)
        if discovery_info:
            discovery.load_platform(hass, component, DOMAIN, discovery_info,
                                    config)
    return True


def get_discovery_info(component_setup, groups):
    """Get discovery info for specified component."""
    discovery_data = {}
    for group in groups:
        groupname = group.attrib['name']
        for product_cfg in component_setup:
            products = group.findall(product_cfg[CONF_XPATH])
            for product in products:
                nodes = product.findall(product_cfg[CONF_NODE])
                for node in nodes:
                    if ('setting' in node.attrib
                            and node.attrib['setting'] == 'yes'):
                        continue
                    ihc_id = int(node.attrib['id'].strip('_'), 0)
                    name = '{}_{}'.format(groupname, ihc_id)
                    device = {
                        'ihc_id': ihc_id,
                        'product': product,
                        'product_cfg': product_cfg}
                    discovery_data[name] = device
    return discovery_data


def setup_service_functions(hass: HomeAssistantType, ihc_controller):
    """Setup the ihc service functions."""
    def set_runtime_value_bool(call):
        """Set a IHC runtime bool value service function."""
        ihc_id = call.data[ATTR_IHC_ID]
        value = call.data[ATTR_VALUE]
        ihc_controller.set_runtime_value_bool(ihc_id, value)

    def set_runtime_value_int(call):
        """Set a IHC runtime integer value service function."""
        ihc_id = call.data[ATTR_IHC_ID]
        value = call.data[ATTR_VALUE]
        ihc_controller.set_runtime_value_int(ihc_id, value)

    def set_runtime_value_float(call):
        """Set a IHC runtime float value service function."""
        ihc_id = call.data[ATTR_IHC_ID]
        value = call.data[ATTR_VALUE]
        ihc_controller.set_runtime_value_float(ihc_id, value)

    hass.services.register(DOMAIN, SERVICE_SET_RUNTIME_VALUE_BOOL,
                           set_runtime_value_bool,
                           schema=SET_RUNTIME_VALUE_BOOL_SCHEMA)
    hass.services.register(DOMAIN, SERVICE_SET_RUNTIME_VALUE_INT,
                           set_runtime_value_int,
                           schema=SET_RUNTIME_VALUE_INT_SCHEMA)
    hass.services.register(DOMAIN, SERVICE_SET_RUNTIME_VALUE_FLOAT,
                           set_runtime_value_float,
                           schema=SET_RUNTIME_VALUE_FLOAT_SCHEMA)


def validate_name(config):
    """Validate device name."""
    if CONF_NAME in config:
        return config
    ihcid = config[CONF_ID]
    name = 'ihc_{}'.format(ihcid)
    config[CONF_NAME] = name
    return config
