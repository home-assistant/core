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
    vol.Optional(CONF_AUTOSETUP, default='False'): cv.boolean,
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
    if config.get(CONF_AUTOSETUP):
        def setup_product(ihc_id, name, product, product_cfg):
            """Product setup callback."""
            sensor = IhcLight(ihc, name, ihc_id, product_cfg[CONF_DIMMABLE],
                              product)
            devices.append(sensor)
        ihc.product_auto_setup('light', setup_product)

    lights = config.get(CONF_LIGHTS)
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
    def should_poll(self) -> bool:
        """No polling needed for a ihc light."""
        return False

    @property
    def available(self) -> bool:
        """Return availability."""
        return True

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
        self._state = True
        if ATTR_BRIGHTNESS in kwargs:
            self._brightness = kwargs[ATTR_BRIGHTNESS]

        if self._dimmable:
            if self._brightness == 0:
                self._brightness = 255
            self.ihc.ihc_controller.set_runtime_value_int(
                self._ihc_id, int(self._brightness * 100 / 255))
        else:
            self.ihc.ihc_controller.set_runtime_value_bool(self._ihc_id, True)
        # As we have disabled polling, we need to inform
        # Home Assistant about updates in our state ourselves.
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs) -> None:
        """Turn the light off."""
        self._state = False

        if self._dimmable:
            self.ihc.ihc_controller.set_runtime_value_int(self._ihc_id, 0)
        else:
            self.ihc.ihc_controller.set_runtime_value_bool(self._ihc_id, False)
        # As we have disabled polling, we need to inform
        # Home Assistant about updates in our state ourselves.
        self.schedule_update_ha_state()

    def on_ihc_change(self, ihc_id, value):
        """Callback from Ihc notifications."""
        if type(value) is int:
            self._dimmable = True
            self._brightness = value * 255 / 100
            self._state = self._brightness > 0
        else:
            self._dimmable = False
            self._state = value
        self.schedule_update_ha_state()
