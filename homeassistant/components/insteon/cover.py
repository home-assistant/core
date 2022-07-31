"""Support for Insteon covers via PowerLinc Modem."""
import math
from typing import Any

from homeassistant.components.cover import (
    ATTR_POSITION,
    DOMAIN as COVER_DOMAIN,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import SIGNAL_ADD_ENTITIES
from .insteon_entity import InsteonEntity
from .utils import async_add_insteon_entities


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Insteon covers from a config entry."""

    @callback
    def async_add_insteon_cover_entities(discovery_info=None):
        """Add the Insteon entities for the platform."""
        async_add_insteon_entities(
            hass, COVER_DOMAIN, InsteonCoverEntity, async_add_entities, discovery_info
        )

    signal = f"{SIGNAL_ADD_ENTITIES}_{COVER_DOMAIN}"
    async_dispatcher_connect(hass, signal, async_add_insteon_cover_entities)
    async_add_insteon_cover_entities()


class InsteonCoverEntity(InsteonEntity, CoverEntity):
    """A Class for an Insteon cover entity."""

    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.SET_POSITION
    )

    @property
    def current_cover_position(self) -> int:
        """Return the current cover position."""
        if self._insteon_device_group.value is not None:
            pos = self._insteon_device_group.value
        else:
            pos = 0
        return int(math.ceil(pos * 100 / 255))

    @property
    def is_closed(self) -> bool:
        """Return the boolean response if the node is on."""
        return bool(self.current_cover_position)

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open cover."""
        await self._insteon_device.async_open()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close cover."""
        await self._insteon_device.async_close()

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Set the cover position."""
        position = int(kwargs[ATTR_POSITION] * 255 / 100)
        if position == 0:
            await self._insteon_device.async_close()
        else:
            await self._insteon_device.async_open(
                open_level=position, group=self._insteon_device_group.group
            )
