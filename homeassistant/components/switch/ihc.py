"""IHC switch platform.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.ihc/
"""
from xml.etree.ElementTree import Element

import voluptuous as vol

from homeassistant.components.ihc import (
    validate_name, IHC_DATA, IHC_CONTROLLER, IHC_INFO)
from homeassistant.components.ihc.ihcdevice import IHCDevice
from homeassistant.components.switch import SwitchDevice, PLATFORM_SCHEMA
from homeassistant.const import CONF_ID, CONF_NAME, CONF_SWITCHES
import homeassistant.helpers.config_validation as cv

DEPENDENCIES = ['ihc']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_SWITCHES, default=[]):
        vol.All(cv.ensure_list, [
            vol.All({
                vol.Required(CONF_ID): cv.positive_int,
                vol.Optional(CONF_NAME): cv.string,
            }, validate_name)
        ])
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the ihc switch platform."""
    ihc_controller = hass.data[IHC_DATA][IHC_CONTROLLER]
    info = hass.data[IHC_DATA][IHC_INFO]
    devices = []
    if discovery_info:
        for name, device in discovery_info.items():
            ihc_id = device['ihc_id']
            product = device['product']
            switch = IHCSwitch(ihc_controller, name, ihc_id, info, product)
            devices.append(switch)
    else:
        switches = config[CONF_SWITCHES]
        for switch in switches:
            ihc_id = switch[CONF_ID]
            name = switch[CONF_NAME]
            sensor = IHCSwitch(ihc_controller, name, ihc_id, info)
            devices.append(sensor)

    add_devices(devices)


class IHCSwitch(IHCDevice, SwitchDevice):
    """IHC Switch."""

    def __init__(self, ihc_controller, name: str, ihc_id: int,
                 info: bool, product: Element=None) -> None:
        """Initialize the IHC switch."""
        super().__init__(ihc_controller, name, ihc_id, product)
        self._state = False

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._state

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        self.ihc_controller.set_runtime_value_bool(self.ihc_id, True)

    def turn_off(self, **kwargs):
        """Turn the device off."""
        self.ihc_controller.set_runtime_value_bool(self.ihc_id, False)

    def on_ihc_change(self, ihc_id, value):
        """Callback when the ihc resource changes."""
        self._state = value
        self.schedule_update_ha_state()
