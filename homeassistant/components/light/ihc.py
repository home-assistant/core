"""IHC light platform.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.ihc/
"""
import voluptuous as vol

from homeassistant.components.ihc import (
    validate_name, IHC_DATA, IHC_CONTROLLER, IHC_INFO)
from homeassistant.components.ihc.const import CONF_DIMMABLE
from homeassistant.components.ihc.ihcdevice import IHCDevice
from homeassistant.components.light import (
    ATTR_BRIGHTNESS, SUPPORT_BRIGHTNESS, PLATFORM_SCHEMA, Light)
from homeassistant.const import CONF_ID, CONF_NAME, CONF_LIGHTS
import homeassistant.helpers.config_validation as cv

DEPENDENCIES = ['ihc']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_LIGHTS, default=[]):
        vol.All(cv.ensure_list, [
            vol.All({
                vol.Required(CONF_ID): cv.positive_int,
                vol.Optional(CONF_NAME): cv.string,
                vol.Optional(CONF_DIMMABLE, default=False): cv.boolean,
            }, validate_name)
        ])
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the IHC lights platform."""
    ihc_controller = hass.data[IHC_DATA][IHC_CONTROLLER]
    info = hass.data[IHC_DATA][IHC_INFO]
    devices = []
    if discovery_info:
        for name, device in discovery_info.items():
            ihc_id = device['ihc_id']
            product_cfg = device['product_cfg']
            product = device['product']
            light = IhcLight(ihc_controller, name, ihc_id, info,
                             product_cfg[CONF_DIMMABLE], product)
            devices.append(light)
    else:
        lights = config[CONF_LIGHTS]
        for light in lights:
            ihc_id = light[CONF_ID]
            name = light[CONF_NAME]
            dimmable = light[CONF_DIMMABLE]
            device = IhcLight(ihc_controller, name, ihc_id, info, dimmable)
            devices.append(device)

    add_entities(devices)


class IhcLight(IHCDevice, Light):
    """Representation of a IHC light.

    For dimmable lights, the associated IHC resource should be a light
    level (integer). For non dimmable light the IHC resource should be
    an on/off (boolean) resource
    """

    def __init__(self, ihc_controller, name, ihc_id: int, info: bool,
                 dimmable=False, product=None) -> None:
        """Initialize the light."""
        super().__init__(ihc_controller, name, ihc_id, info, product)
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
            self.ihc_controller.set_runtime_value_int(
                self.ihc_id, int(brightness * 100 / 255))
        else:
            self.ihc_controller.set_runtime_value_bool(self.ihc_id, True)

    def turn_off(self, **kwargs) -> None:
        """Turn the light off."""
        if self._dimmable:
            self.ihc_controller.set_runtime_value_int(self.ihc_id, 0)
        else:
            self.ihc_controller.set_runtime_value_bool(self.ihc_id, False)

    def on_ihc_change(self, ihc_id, value):
        """Handle IHC notifications."""
        if isinstance(value, bool):
            self._dimmable = False
            self._state = value != 0
        else:
            self._dimmable = True
            self._state = value > 0
            if self._state:
                self._brightness = int(value * 255 / 100)
        self.schedule_update_ha_state()
