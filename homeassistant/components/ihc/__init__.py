"""
IHC platform.
"""
# pylint: disable=too-many-arguments, too-many-instance-attributes, bare-except
import time
import logging
import os.path
import asyncio
import xml.etree.ElementTree
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.const import CONF_URL, CONF_USERNAME, CONF_PASSWORD
from homeassistant.config import load_yaml_config_file

from homeassistant.components.ihc import const

REQUIREMENTS = ['ihcsdk==2.1.0']
DOMAIN = 'ihc'

CONF_INFO = 'info'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_URL): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_INFO): cv.boolean
    }),
}, extra=vol.ALLOW_EXTRA)

_LOGGER = logging.getLogger(__name__)

def setup(hass, config):
    """Setyp the IHC platform."""
    from ihcsdk.ihccontroller import IHCController
    url = config[DOMAIN].get(CONF_URL)
    username = config[DOMAIN].get(CONF_USERNAME)
    password = config[DOMAIN].get(CONF_PASSWORD)
    ihc = IHCController(url, username, password)
    ihc.info = config[DOMAIN].get(CONF_INFO)

    if  not ihc.authenticate():
        _LOGGER.error("Unable to authenticate on ihc controller. Username/password may be wrong")
        return False

    hass.data[DOMAIN] = IHCPlatform(ihc)

    #Service functions

    def set_runtime_value_bool(call):
        """Set a IHC runtime bool value service function """
        ihcid = int(call.data.get('ihcid', 0))
        value = bool(call.data.get('value', 0))
        ihc.set_runtime_value_bool(ihcid, value)

    def set_runtime_value_int(call):
        """Set a IHC runtime integer value service function """
        ihcid = int(call.data.get('ihcid', 0))
        value = int(call.data.get('value', 0))
        ihc.set_runtime_value_int(ihcid, value)

    def set_runtime_value_float(call):
        """Set a IHC runtime float value service function """
        ihcid = int(call.data.get('ihcid', 0))
        value = float(call.data.get('value', 0))
        ihc.set_runtime_value_float(ihcid, value)

    descriptions = load_yaml_config_file(
        os.path.join(os.path.dirname(__file__), 'services.yaml'))

    hass.services.register(DOMAIN, const.SERVICE_SET_RUNTIME_VALUE_BOOL,
                           set_runtime_value_bool,
                           descriptions[const.SERVICE_SET_RUNTIME_VALUE_BOOL])
    hass.services.register(DOMAIN, const.SERVICE_SET_RUNTIME_VALUE_INT,
                           set_runtime_value_int,
                           descriptions[const.SERVICE_SET_RUNTIME_VALUE_INT])
    hass.services.register(DOMAIN, const.SERVICE_SET_RUNTIME_VALUE_FLOAT,
                           set_runtime_value_float,
                           descriptions[const.SERVICE_SET_RUNTIME_VALUE_FLOAT])

    #hass.http.register_view(IHCSetupView())
    return True



class IHCPlatform:
    """Wraps the IHCController for caching of ihc project and autosetup"""
    def __init__(self, ihccontroller):
        self.ihc = ihccontroller
        project = self.ihc.get_project()
        self._project = xml.etree.ElementTree.fromstring(project)
        self._groups = self._project.findall(r'.//group')

    def get_project_xml(self):
        """Get the cached ihc project as xml"""
        return self._project

    def get_groups_xml(self):
        """Get the groups from the ihc project and cache the result"""
        return self._groups

    def autosetup(self, productautosetup, callback):
        """Do autosetup of a component usign the specified productautosetup"""
        groups = self.get_groups_xml()
        for group in groups:
            groupname = group.attrib['name']
            for productcfg in productautosetup:
                products = group.findall(productcfg['xpath'])
                for product in products:
                    nodes = product.findall(productcfg['node'])
                    for node in nodes:
                        if 'setting' in node.attrib and node.attrib['setting'] == 'yes':
                            continue
                        ihcid = int(node.attrib['id'].strip('_'), 0)
                        name = groupname + "_" + str(ihcid)
                        callback(ihcid, name, product, productcfg)

def get_ihc_platform(hass) -> IHCPlatform:
    """Get the ihc platform instance from the hass configuration
    This is a singleton object.
    """
    while not DOMAIN in hass.data:
        time.sleep(0.1)
    return hass.data[DOMAIN]
