"""Support for Insteon covers via PowerLinc Modem."""
import logging
import math

from homeassistant.components.cover import (
    ATTR_POSITION,
    DOMAIN as COVER_DOMAIN,
    SUPPORT_CLOSE,
    SUPPORT_OPEN,
    SUPPORT_SET_POSITION,
    CoverEntity,
)
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import SIGNAL_ADD_ENTITIES
from .insteon_entity import InsteonEntity
from .utils import async_add_insteon_entities

_LOGGER = logging.getLogger(__name__)

SUPPORTED_FEATURES = SUPPORT_OPEN | SUPPORT_CLOSE | SUPPORT_SET_POSITION


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Insteon covers from a config entry."""

    def add_entities(discovery_info=None):
        """Add the Insteon entities for the platform."""
        async_add_insteon_entities(
            hass, COVER_DOMAIN, InsteonCoverEntity, async_add_entities, discovery_info
        )

    signal = f"{SIGNAL_ADD_ENTITIES}_{COVER_DOMAIN}"
    async_dispatcher_connect(hass, signal, add_entities)
    add_entities()


class InsteonCoverEntity(InsteonEntity, CoverEntity):
    """A Class for an Insteon cover entity."""

    @property
    def current_cover_position(self):
        """Return the current cover position."""
        if self._insteon_device_group.value is not None:
            pos = self._insteon_device_group.value
        else:
            pos = 0
        return int(math.ceil(pos * 100 / 255))

    @property
    def supported_features(self):
        """Return the supported features for this entity."""
        return SUPPORTED_FEATURES

    @property
    def is_closed(self):
        """Return the boolean response if the node is on."""
        return bool(self.current_cover_position)

    async def async_open_cover(self, **kwargs):
        """Open cover."""
        await self._insteon_device.async_open()

    async def async_close_cover(self, **kwargs):
        """Close cover."""
        await self._insteon_device.async_close()

    async def async_set_cover_position(self, **kwargs):
        """Set the cover position."""
        position = int(kwargs[ATTR_POSITION] * 255 / 100)
        if position == 0:
            await self._insteon_device.async_close()
        else:
            await self._insteon_device.async_open(
                open_level=position, group=self._insteon_device_group.group
            )
