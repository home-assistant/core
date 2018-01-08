"""IHC light platform.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.ihc/
"""
# pylint: disable=unidiomatic-typecheck
from xml.etree.ElementTree import Element

import voluptuous as vol

from homeassistant.components.ihc import validate_name, IHC_DATA
from homeassistant.components.ihc.const import CONF_AUTOSETUP, CONF_DIMMABLE
from homeassistant.components.ihc.ihcdevice import IHCDevice
from homeassistant.components.light import (
    ATTR_BRIGHTNESS, SUPPORT_BRIGHTNESS, PLATFORM_SCHEMA, Light)
from homeassistant.const import CONF_ID, CONF_NAME, CONF_LIGHTS
import homeassistant.helpers.config_validation as cv

DEPENDENCIES = ['ihc']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_AUTOSETUP, default=False): cv.boolean,
    vol.Optional(CONF_LIGHTS, default=[]):
        vol.All(cv.ensure_list, [
            vol.All({
                vol.Required(CONF_ID): cv.positive_int,
                vol.Optional(CONF_NAME): cv.string,
                vol.Optional(CONF_DIMMABLE, default=False): cv.boolean,
            }, validate_name)
        ])
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the ihc lights platform."""
    ihc = hass.data[IHC_DATA]
    devices = []
    if config[CONF_AUTOSETUP]:
        def setup_product(ihc_id, name, product, product_cfg):
            """Product setup callback."""
            sensor = IhcLight(ihc, name, ihc_id, product_cfg[CONF_DIMMABLE],
                              product)
            devices.append(sensor)
        ihc.product_auto_setup('light', setup_product)

    lights = config[CONF_LIGHTS]
    for light in lights:
        ihc_id = light[CONF_ID]
        name = light[CONF_NAME]
        dimmable = light[CONF_DIMMABLE]
        device = IhcLight(ihc, name, ihc_id, dimmable)
        devices.append(device)

    add_devices(devices)


class IhcLight(IHCDevice, Light):
    """Representation of a IHC light."""

    def __init__(self, ihccontroller, name, ihcid, dimmable=False,
                 product: Element=None):
        """Initialize the light."""
        super().__init__(ihccontroller, name, ihcid, product)
        self._brightness = 0
        self._dimmable = dimmable
        self._state = None

    @property
    def brightness(self) -> int:
        """Return the brightness of this light between 0..255."""
        return self._brightness

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        return self._state

    @property
    def supported_features(self):
        """Flag supported features."""
        if self._dimmable:
            return SUPPORT_BRIGHTNESS
        return 0

    def turn_on(self, **kwargs) -> None:
        """Turn the light on."""
        if ATTR_BRIGHTNESS in kwargs:
            brightness = kwargs[ATTR_BRIGHTNESS]
        else:
            brightness = self._brightness
            if brightness == 0:
                brightness = 255

        if self._dimmable:
            self.ihc.ihc_controller.set_runtime_value_int(
                self.ihc_id, int(brightness * 100 / 255))
        else:
            self.ihc.ihc_controller.set_runtime_value_bool(self.ihc_id, True)

    def turn_off(self, **kwargs) -> None:
        """Turn the light off."""
        if self._dimmable:
            self.ihc.ihc_controller.set_runtime_value_int(self.ihc_id, 0)
        else:
            self.ihc.ihc_controller.set_runtime_value_bool(self.ihc_id, False)

    def on_ihc_change(self, ihc_id, value):
        """Callback from Ihc notifications."""
        if type(value) is int:
            self._dimmable = True
            self._state = value > 0
            if self._state:
                self._brightness = int(value * 255 / 100)
        else:
            self._dimmable = False
            self._state = value != 0
        self.schedule_update_ha_state()
