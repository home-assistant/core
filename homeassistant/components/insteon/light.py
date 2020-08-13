"""Support for Insteon lights via PowerLinc Modem."""
import logging

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    DOMAIN as LIGHT_DOMAIN,
    SUPPORT_BRIGHTNESS,
    LightEntity,
)
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import SIGNAL_ADD_ENTITIES
from .insteon_entity import InsteonEntity
from .utils import async_add_insteon_entities

_LOGGER = logging.getLogger(__name__)

MAX_BRIGHTNESS = 255


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Insteon lights from a config entry."""

    def add_entities(discovery_info=None):
        """Add the Insteon entities for the platform."""
        async_add_insteon_entities(
            hass, LIGHT_DOMAIN, InsteonDimmerEntity, async_add_entities, discovery_info
        )

    signal = f"{SIGNAL_ADD_ENTITIES}_{LIGHT_DOMAIN}"
    async_dispatcher_connect(hass, signal, add_entities)
    add_entities()


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
