"""
Support for control of ElkM1 lighting (X10, UPB, etc).

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.elkm1/
"""

from homeassistant.components.light import (
    ATTR_BRIGHTNESS, SUPPORT_BRIGHTNESS, Light)
from homeassistant.components.elkm1 import (
    DOMAIN as ELK_DOMAIN, ElkEntity, create_elk_entities)

DEPENDENCIES = [ELK_DOMAIN]


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the Elk light platform."""
    if discovery_info is None:
        return
    elk = hass.data[ELK_DOMAIN]['elk']
    async_add_entities(
        create_elk_entities(hass, elk.lights, 'plc', ElkLight, []), True)


class ElkLight(ElkEntity, Light):
    """Elk lighting device."""

    def __init__(self, element, elk, elk_data):
        """Initialize light."""
        super().__init__(element, elk, elk_data)
        self._brightness = self._element.status

    @property
    def brightness(self):
        """Get the brightness."""
        return self._brightness

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_BRIGHTNESS

    @property
    def is_on(self) -> bool:
        """Get the current brightness."""
        return self._brightness != 0

    def _element_changed(self, element, changeset):
        status = self._element.status if self._element.status != 1 else 100
        self._brightness = round(status * 2.55)

    async def async_turn_on(self, **kwargs):
        """Turn on the light."""
        self._element.level(round(kwargs.get(ATTR_BRIGHTNESS, 255) / 2.55))

    async def async_turn_off(self, **kwargs):
        """Turn off the light."""
        self._element.level(0)
