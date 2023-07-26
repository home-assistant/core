"""Support for Velbus covers."""
from __future__ import annotations

from typing import Any

from duotecno.unit import DuoswitchUnit

from homeassistant.components.cover import (
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import DuotecnoEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the duoswitch endities."""
    cntrl = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        DuotecnoCover(channel) for channel in cntrl.get_units("DuoSwitchUnit")
    )


class DuotecnoCover(DuotecnoEntity, CoverEntity):
    """Representation a Velbus cover."""

    _unit: DuoswitchUnit

    def __init__(self, unit: DuoswitchUnit) -> None:
        """Initialize the cover."""
        super().__init__(unit)
        self._attr_supported_features = (
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

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        try:
            await self._unit.open()
        except OSError as err:
            raise HomeAssistantError(
                "Transmit for the open_cover packet failed"
            ) from err

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        try:
            await self._unit.close()
        except OSError as err:
            raise HomeAssistantError(
                "Transmit for the close_cover packet failed"
            ) from err

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        try:
            await self._unit.stop()
        except OSError as err:
            raise HomeAssistantError(
                "Transmit for the stop_cover packet failed"
            ) from err
