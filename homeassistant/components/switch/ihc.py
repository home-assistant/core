"""
IHC switch platform that implements a switch.
"""
# pylint: disable=too-many-arguments, too-many-instance-attributes, bare-except, unused-argument, missing-docstring
import logging
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.components.switch import (SwitchDevice, PLATFORM_SCHEMA)
from homeassistant.const import CONF_ID, CONF_NAME, CONF_SWITCHES

from homeassistant.components.ihc.const import CONF_AUTOSETUP
from homeassistant.components.ihc import get_ihc_platform
from homeassistant.components.ihc.ihcdevice import IHCDevice

DEPENDENCIES = ['ihc']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_AUTOSETUP, default='False'): cv.boolean,
    vol.Optional(CONF_SWITCHES) :
        [{
            vol.Required(CONF_ID): cv.positive_int,
            vol.Optional(CONF_NAME): cv.string,
        }]
})

PRODUCTAUTOSETUP = [
    # Wireless Plug outlet
    {'xpath': './/product_airlink[@product_identifier="_0x4201"]',
     'node': 'airlink_relay'},
    # Dataline universal relay
    {'xpath': './/product_airlink[@product_identifier="_0x4203"]',
     'node': 'airlink_relay'},
    # Dataline plug outlet
    {'xpath': './/product_dataline[@product_identifier="_0x2201"]',
     'node': 'dataline_output'},
    ]


_LOGGER = logging.getLogger(__name__)

_IHCSWITCHES = {}

def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Setup the ihc switch platform."""
    ihcplatform = get_ihc_platform(hass)
    devices = []
    if config.get('autosetup'):
        auto_setup(ihcplatform, devices)

    switches = config.get(CONF_SWITCHES)
    if switches:
        _LOGGER.info("Adding IHC Switches")
        for switch in switches:
            ihcid = switch[CONF_ID]
            name = switch[CONF_NAME] if CONF_NAME in switch else "ihc_" + str(ihcid)
            add_switch(devices, ihcplatform.ihc, int(ihcid), name, True)

    add_devices_callback(devices)
    # Start notification after device har been added
    for device in devices:
        device.ihc.add_notify_event(device.get_ihcid(), device.on_ihc_change, True)

def auto_setup(ihcplatform, devices):
    """Auto setup switched from the ihc project file."""
    _LOGGER.info("Auto setup for IHC switch")
    def setup_product(ihcid, name, product, productcfg):
        add_switch_from_node(devices, ihcplatform.ihc, ihcid, name, product)
    ihcplatform.autosetup(PRODUCTAUTOSETUP, setup_product)

class IHCSwitch(IHCDevice, SwitchDevice):
    """IHC Switch."""
    def __init__(self, ihccontroller, name: str, ihcid: int,
                 ihcname: str, ihcnote: str, ihcposition: str):
        IHCDevice.__init__(self, ihccontroller, name, ihcid, ihcname, ihcnote, ihcposition)
        self._state = False
        self._icon = None
        self._assumed = False

    @property
    def should_poll(self):
        return False

    @property
    def icon(self):
        """Return the icon to use for device if any."""
        return self._icon

    @property
    def assumed_state(self):
        """Return if the state is based on assumptions."""
        return self._assumed

    @property
    def current_power_w(self):
        """Return the current power usage in W."""
        return 0

    @property
    def today_energy_kwh(self):
        """Return the today total energy usage in kWh."""
        return 0

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._state

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        self._state = True
        self.ihc.set_runtime_value_bool(self._ihcid, True)
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Turn the device off."""
        self._state = False
        self.ihc.set_runtime_value_bool(self._ihcid, False)
        self.schedule_update_ha_state()

    def on_ihc_change(self, ihcid, value):
        """Callback when the ihc resource changes."""
        try:
            self._state = value
            self.schedule_update_ha_state()
        except:
            pass


def add_switch_from_node(devices, ihccontroller, ihcid: int, name: str, product) -> IHCSwitch:
    """Add a IHC switch form the a product in the project."""
    ihcname = product.attrib['name']
    ihcnote = product.attrib['note']
    ihcposition = product.attrib['position']
    return add_switch(devices, ihccontroller, ihcid, name, False, ihcname, ihcnote, ihcposition)

def add_switch(devices, ihccontroller, ihcid: int, name: str, overwrite: bool = False,
               ihcname: str = "", ihcnote: str = "", ihcposition: str = "") -> IHCSwitch:
    """Add a new ihc switch"""
    if ihcid in _IHCSWITCHES:
        switch = _IHCSWITCHES[ihcid]
        if overwrite:
            switch.set_name(name)
            _LOGGER.info("IHC switch set name: " + name + " " + str(ihcid))
    else:
        switch = IHCSwitch(ihccontroller, name, ihcid, ihcname, ihcnote, ihcposition)
        _IHCSWITCHES[ihcid] = switch
        devices.append(switch)
        _LOGGER.info("IHC switch added: " + name + " " + str(ihcid))
    return switch
