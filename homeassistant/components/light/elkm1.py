"""
Support for control of ElkM1 lighting (X10, UPB, etc).

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.elkm1/
"""

from homeassistant.components.light import (ATTR_BRIGHTNESS,
                                            SUPPORT_BRIGHTNESS, Light)
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNKNOWN

from homeassistant.components.elkm1 import (DOMAIN, ElkDeviceBase,
                                            create_elk_devices)

DEPENDENCIES = [DOMAIN]


# pylint: disable=unused-argument
async def async_setup_platform(hass, config, async_add_devices,
                               discovery_info):
    """Setup the Elk light platform."""
    elk = hass.data[DOMAIN]['elk']
    async_add_devices(create_elk_devices(hass, elk.lights,
                                         'plc', ElkLight, []), True)
    return True


class ElkLight(ElkDeviceBase, Light):
    """Elk lighting device."""
    def __init__(self, device, hass, config):
        """Initialize light."""
        ElkDeviceBase.__init__(self, 'light', device, hass, config)
        self._brightness = self._element.status
        self._state = STATE_UNKNOWN

    @property
    def brightness(self):
        """Get the brightness of the PLC light."""
        return self._brightness

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_BRIGHTNESS

    # pylint: disable=unused-argument
    def _element_changed(self, element, changeset):
        """Callback handler from the Elk."""
        status = self._element.status if self._element.status != 1 else 100
        self._state = STATE_OFF if status == 0 else STATE_ON
        self._brightness = round(status * 2.55)

    @property
    def is_on(self) -> bool:
        """Is there light?"""
        return self._brightness != 0

    async def async_turn_on(self, **kwargs):
        """Let there be light!"""
        self._element.level(round(kwargs.get(ATTR_BRIGHTNESS, 255) / 2.55))

    async def async_turn_off(self, **kwargs):
        """In the darkness..."""
        self._element.level(0)
