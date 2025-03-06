"""Support for Velbus covers."""

from __future__ import annotations

from typing import Any

from duotecno.unit import DuoswitchUnit

from homeassistant.components.cover import CoverEntity, CoverEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import DuotecnoConfigEntry
from .entity import DuotecnoEntity, api_call


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DuotecnoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the duoswitch endities."""
    async_add_entities(
        DuotecnoCover(channel)
        for channel in entry.runtime_data.get_units("DuoswitchUnit")
    )


class DuotecnoCover(DuotecnoEntity, CoverEntity):
    """Representation a Velbus cover."""

    _unit: DuoswitchUnit
    _attr_supported_features = (
        CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
    )

    @property
    def is_closed(self) -> bool | None:
        """Return if the cover is closed."""
        return self._unit.is_closed()

    @property
    def is_opening(self) -> bool:
        """Return if the cover is opening."""
        return self._unit.is_opening()

    @property
    def is_closing(self) -> bool:
        """Return if the cover is closing."""
        return self._unit.is_closing()

    @api_call
    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        await self._unit.open()

    @api_call
    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        await self._unit.close()

    @api_call
    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        await self._unit.stop()
