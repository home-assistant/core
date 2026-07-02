"""PowerShades cover platform."""

import logging
from typing import Any

from homeassistant.components.cover import (
    ATTR_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import PowerShadesConfigEntry, PowerShadesCoordinator
from .entity import PowerShadesEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PowerShadesConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up PowerShades cover from a config entry."""
    async_add_entities([PowerShadesCover(entry.runtime_data)])


class PowerShadesCover(PowerShadesEntity, CoverEntity):
    """PowerShades cover entity."""

    _attr_name = None
    _attr_device_class = CoverDeviceClass.SHADE
    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.STOP
        | CoverEntityFeature.SET_POSITION
    )

    def __init__(self, coordinator: PowerShadesCoordinator) -> None:
        """Initialize the PowerShades cover."""
        super().__init__(coordinator, "cover")

    @property
    def current_cover_position(self) -> int | None:
        """Return the current position of the cover."""
        return self.coordinator.data.position

    @property
    def is_closed(self) -> bool | None:
        """Return if the cover is closed."""
        position = self.coordinator.data.position
        if position is None:
            return None
        return position == 0

    @property
    def is_opening(self) -> bool:
        """Return if the cover is opening."""
        data = self.coordinator.data
        return (
            data.target_position is not None
            and data.position is not None
            and data.target_position > data.position
        )

    @property
    def is_closing(self) -> bool:
        """Return if the cover is closing."""
        data = self.coordinator.data
        return (
            data.target_position is not None
            and data.position is not None
            and data.target_position < data.position
        )

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        await self.coordinator.async_set_position(100)

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        await self.coordinator.async_set_position(0)

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        await self.coordinator.async_stop()

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        await self.coordinator.async_set_position(kwargs[ATTR_POSITION])
