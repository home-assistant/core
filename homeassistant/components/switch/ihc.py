"""IHC switch platform.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.ihc/
"""
from xml.etree.ElementTree import Element

import voluptuous as vol

from homeassistant.components.ihc import validate_name, IHC_DATA
from homeassistant.components.ihc.const import CONF_AUTOSETUP
from homeassistant.components.ihc.ihcdevice import IHCDevice
from homeassistant.components.switch import (SwitchDevice, PLATFORM_SCHEMA)
from homeassistant.const import CONF_ID, CONF_NAME, CONF_SWITCHES
import homeassistant.helpers.config_validation as cv

DEPENDENCIES = ['ihc']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_AUTOSETUP, default=False): cv.boolean,
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
    ihc = hass.data[IHC_DATA]
    devices = []
    if config[CONF_AUTOSETUP]:
        def setup_product(ihc_id, name, product, product_cfg):
            """Product setup callback."""
            sensor = IHCSwitch(ihc, name, ihc_id, product)
            devices.append(sensor)
        ihc.product_auto_setup('switch', setup_product)

    switches = config[CONF_SWITCHES]
    for switch in switches:
        ihc_id = switch[CONF_ID]
        name = switch[CONF_NAME]
        sensor = IHCSwitch(ihc, name, ihc_id)
        devices.append(sensor)

    add_devices(devices)


class IHCSwitch(IHCDevice, SwitchDevice):
    """IHC Switch."""

    def __init__(self, ihc, name: str, ihc_id: int, product: Element=None):
        """Initialize the IHC switch."""
        super().__init__(ihc, name, ihc_id, product)
        self._state = False

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._state

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        self.ihc.ihc_controller.set_runtime_value_bool(self.ihc_id, True)

    def turn_off(self, **kwargs):
        """Turn the device off."""
        self.ihc.ihc_controller.set_runtime_value_bool(self.ihc_id, False)

    def on_ihc_change(self, ihc_id, value):
        """Callback when the ihc resource changes."""
        self._state = value
        self.schedule_update_ha_state()
