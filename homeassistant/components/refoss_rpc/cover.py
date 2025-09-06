"""Cover for refoss."""

from __future__ import annotations

from typing import Any, cast

from homeassistant.components.cover import (
    ATTR_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import RefossConfigEntry, RefossCoordinator
from .entity import RefossEntity
from .utils import get_refoss_key_ids


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: RefossConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up cover for device."""
    coordinator = config_entry.runtime_data.coordinator
    assert coordinator

    cover_key_ids = get_refoss_key_ids(coordinator.device.status, "cover")

    async_add_entities(RefossCover(coordinator, _id) for _id in cover_key_ids)


class RefossCover(RefossEntity, CoverEntity):
    """Refoss cover entity."""

    _attr_device_class = CoverDeviceClass.SHUTTER
    _attr_supported_features: CoverEntityFeature = (
        CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
    )

    def __init__(self, coordinator: RefossCoordinator, _id: int) -> None:
        """Initialize  cover."""
        super().__init__(coordinator, f"cover:{_id}")
        self._id = _id
        if self.status["cali_state"] == "success":
            self._attr_supported_features |= CoverEntityFeature.SET_POSITION

    @property
    def current_cover_position(self) -> int | None:
        """Position of the cover."""
        if not self.status["cali_state"] or self.status["cali_state"] != "success":
            return None
        return cast(int, self.status["current_pos"])

    @property
    def is_closed(self) -> bool | None:
        """If cover is closed."""
        return cast(bool, self.status["state"] == "closed")

    @property
    def is_closing(self) -> bool:
        """Return if the cover is closing."""
        return cast(bool, self.status["state"] == "closing")

    @property
    def is_opening(self) -> bool:
        """Return if the cover is opening."""
        return cast(bool, self.status["state"] == "opening")

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close cover."""
        await self.call_rpc("Cover.Action.Set", {"id": self._id, "action": "close"})

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open cover."""
        await self.call_rpc("Cover.Action.Set", {"id": self._id, "action": "open"})

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        await self.call_rpc(
            "Cover.Pos.Set", {"id": self._id, "pos": kwargs[ATTR_POSITION]}
        )

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        await self.call_rpc("Cover.Action.Set", {"id": self._id, "action": "stop"})
