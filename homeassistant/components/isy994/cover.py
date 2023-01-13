"""Support for ISY covers."""
from __future__ import annotations

from typing import Any, cast

from pyisy.constants import ISY_VALUE_UNKNOWN

from homeassistant.components.cover import (
    ATTR_POSITION,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import _LOGGER, DOMAIN, UOM_8_BIT_RANGE, UOM_BARRIER
from .entity import ISYNodeEntity, ISYProgramEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the ISY cover platform."""
    isy_data = hass.data[DOMAIN][entry.entry_id]
    entities: list[ISYCoverEntity | ISYCoverProgramEntity] = []
    devices: dict[str, DeviceInfo] = isy_data.devices
    for node in isy_data.nodes[Platform.COVER]:
        entities.append(ISYCoverEntity(node, devices.get(node.primary_node)))

    for name, status, actions in isy_data.programs[Platform.COVER]:
        entities.append(ISYCoverProgramEntity(name, status, actions))

    async_add_entities(entities)


class ISYCoverEntity(ISYNodeEntity, CoverEntity):
    """Representation of an ISY cover device."""

    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.SET_POSITION
    )

    @property
    def current_cover_position(self) -> int | None:
        """Return the current cover position."""
        if self._node.status == ISY_VALUE_UNKNOWN:
            return None
        if self._node.uom == UOM_8_BIT_RANGE:
            return round(cast(float, self._node.status) * 100.0 / 255.0)
        return int(sorted((0, self._node.status, 100))[1])

    @property
    def is_closed(self) -> bool | None:
        """Get whether the ISY cover device is closed."""
        if self._node.status == ISY_VALUE_UNKNOWN:
            return None
        return bool(self._node.status == 0)

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Send the open cover command to the ISY cover device."""
        val = 100 if self._node.uom == UOM_BARRIER else None
        if not await self._node.turn_on(val=val):
            _LOGGER.error("Unable to open the cover")

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Send the close cover command to the ISY cover device."""
        if not await self._node.turn_off():
            _LOGGER.error("Unable to close the cover")

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        position = kwargs[ATTR_POSITION]
        if self._node.uom == UOM_8_BIT_RANGE:
            position = round(position * 255.0 / 100.0)
        if not await self._node.turn_on(val=position):
            _LOGGER.error("Unable to set cover position")


class ISYCoverProgramEntity(ISYProgramEntity, CoverEntity):
    """Representation of an ISY cover program."""

    @property
    def is_closed(self) -> bool:
        """Get whether the ISY cover program is closed."""
        return bool(self._node.status)

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Send the open cover command to the ISY cover program."""
        if not await self._actions.run_then():
            _LOGGER.error("Unable to open the cover")

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Send the close cover command to the ISY cover program."""
        if not await self._actions.run_else():
            _LOGGER.error("Unable to close the cover")
