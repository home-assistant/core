"""Support for Insteon lights via PowerLinc Modem."""
import logging

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    DOMAIN,
    SUPPORT_BRIGHTNESS,
    LightEntity,
)

from .insteon_entity import InsteonEntity
from .utils import async_add_insteon_entities

_LOGGER = logging.getLogger(__name__)

MAX_BRIGHTNESS = 255


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Insteon component."""
    async_add_insteon_entities(
        hass, DOMAIN, InsteonDimmerEntity, async_add_entities, discovery_info
    )


class InsteonDimmerEntity(InsteonEntity, LightEntity):
    """A Class for an Insteon light entity."""

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return self._insteon_device_group.value

    @property
    def is_on(self):
        """Return the boolean response if the node is on."""
        return bool(self.brightness)

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_BRIGHTNESS

    async def async_turn_on(self, **kwargs):
        """Turn light on."""
        if ATTR_BRIGHTNESS in kwargs:
            brightness = int(kwargs[ATTR_BRIGHTNESS])
            await self._insteon_device.async_on(
                on_level=brightness, group=self._insteon_device_group.group
            )
        else:
            await self._insteon_device.async_on(group=self._insteon_device_group.group)

    async def async_turn_off(self, **kwargs):
        """Turn light off."""
        await self._insteon_device.async_off(self._insteon_device_group.group)
