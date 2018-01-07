"""IHC component.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/ihc/
"""
import logging
import os.path
import xml.etree.ElementTree
import voluptuous as vol
from voluptuous.error import Error as VoluptuousError

import homeassistant.helpers.config_validation as cv
from homeassistant.components.ihc.const import (
    ATTR_IHC_ID, ATTR_VALUE, CONF_INFO,
    CONF_BINARY_SENSOR, CONF_LIGHT, CONF_SENSOR, CONF_SWITCH,
    CONF_XPATH, CONF_NODE, CONF_DIMMABLE, CONF_INVERTING,
    SERVICE_SET_RUNTIME_VALUE_BOOL, SERVICE_SET_RUNTIME_VALUE_INT,
    SERVICE_SET_RUNTIME_VALUE_FLOAT)
from homeassistant.config import load_yaml_config_file
from homeassistant.const import (
    CONF_URL, CONF_USERNAME, CONF_PASSWORD, CONF_ID, CONF_NAME,
    CONF_UNIT_OF_MEASUREMENT, CONF_TYPE)
from homeassistant.helpers.typing import HomeAssistantType

REQUIREMENTS = ['ihcsdk==2.1.0']
DOMAIN = 'ihc'
IHC_DATA = 'ihc'

AUTO_SETUP_YAML = 'ihc_auto_setup.yaml'


CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_URL): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_INFO): cv.boolean
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
                vol.Optional(CONF_TYPE, default='Temperature'): cv.string,
                vol.Optional(CONF_UNIT_OF_MEASUREMENT,
                             default='°C'): cv.string,
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
    vol.Required(ATTR_VALUE): float
})

_LOGGER = logging.getLogger(__name__)


def setup(hass, config):
    """Setup the IHC component."""
    from ihcsdk.ihccontroller import IHCController
    conf = config[DOMAIN]
    url = conf.get(CONF_URL)
    username = conf.get(CONF_USERNAME)
    password = conf.get(CONF_PASSWORD)
    ihc_controller = IHCController(url, username, password)

    if not ihc_controller.authenticate():
        _LOGGER.error("Unable to authenticate on ihc controller.")
        return False

    ihc = Ihc(hass, ihc_controller)
    ihc.info = conf.get(CONF_INFO)
    hass.data[IHC_DATA] = ihc

    # Service functions

    def set_runtime_value_bool(call):
        """Set a IHC runtime bool value service function."""
        ihc_id = int(call.data.get(ATTR_IHC_ID, 0))
        value = bool(call.data.get(ATTR_VALUE, 0))
        ihc_controller.set_runtime_value_bool(ihc_id, value)

    def set_runtime_value_int(call):
        """Set a IHC runtime integer value service function."""
        ihcid = int(call.data.get(ATTR_IHC_ID, 0))
        value = int(call.data.get(ATTR_VALUE, 0))
        ihc_controller.set_runtime_value_int(ihcid, value)

    def set_runtime_value_float(call):
        """Set a IHC runtime float value service function."""
        ihcid = int(call.data.get(ATTR_IHC_ID, 0))
        value = float(call.data.get(ATTR_VALUE, 0))
        ihc_controller.set_runtime_value_float(ihcid, value)

    descriptions = load_yaml_config_file(
        os.path.join(os.path.dirname(__file__), 'services.yaml'))

    hass.services.register(DOMAIN, SERVICE_SET_RUNTIME_VALUE_BOOL,
                           set_runtime_value_bool,
                           descriptions[SERVICE_SET_RUNTIME_VALUE_BOOL],
                           schema=SET_RUNTIME_VALUE_BOOL_SCHEMA)
    hass.services.register(DOMAIN, SERVICE_SET_RUNTIME_VALUE_INT,
                           set_runtime_value_int,
                           descriptions[SERVICE_SET_RUNTIME_VALUE_INT],
                           schema=SET_RUNTIME_VALUE_INT_SCHEMA)
    hass.services.register(DOMAIN, SERVICE_SET_RUNTIME_VALUE_FLOAT,
                           set_runtime_value_float,
                           descriptions[SERVICE_SET_RUNTIME_VALUE_FLOAT],
                           schema=SET_RUNTIME_VALUE_FLOAT_SCHEMA)
    return True


class Ihc:
    """Wraps the IHCController for caching of ihc project and autosetup."""

    def __init__(self, hass: HomeAssistantType, ihc_controller):
        """Initialize the caching of the project."""
        self.ihc_controller = ihc_controller
        self.info = False
        project = self.ihc_controller.get_project()
        if not project:
            _LOGGER.error("Unable to read project from ihc controller.")
            return
        self.project = xml.etree.ElementTree.fromstring(project)
        # We will cache the groups for faster autosetup
        self._groups = self.project.findall(r'.//group')
        # if a auto setup file exist in the configuration it will override
        yaml_path = hass.config.path(AUTO_SETUP_YAML)
        if not os.path.isfile(yaml_path):
            yaml_path = os.path.join(os.path.dirname(__file__),
                                     AUTO_SETUP_YAML)
        yaml = load_yaml_config_file(yaml_path)
        try:
            self.auto_setup_conf = AUTO_SETUP_SCHEMA(yaml)
        except VoluptuousError as exception:
            _LOGGER.error("Invalid IHC auto setup data: %s", exception)
            self.auto_setup_conf = None

    def product_auto_setup(self, component, setup_product):
        """Do autosetup of a component from the IHC project."""
        if not self.auto_setup_conf:
            return
        component_setup = self.auto_setup_conf[component]
        for group in self._groups:
            groupname = group.attrib['name']
            for product_cfg in component_setup:
                products = group.findall(product_cfg['xpath'])
                for product in products:
                    nodes = product.findall(product_cfg['node'])
                    for node in nodes:
                        if ('setting' in node.attrib
                                and node.attrib['setting'] == 'yes'):
                            continue
                        ihc_id = int(node.attrib['id'].strip('_'), 0)
                        name = groupname + "_" + str(ihc_id)
                        setup_product(ihc_id, name, product, product_cfg)


def validate_name(config):
    """Validate device name."""
    if CONF_NAME in config:
        return config
    ihcid = config[CONF_ID]
    name = 'ihc_{}'.format(ihcid)
    config[CONF_NAME] = name
    return config
