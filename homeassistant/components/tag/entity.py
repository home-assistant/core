"""The Tag integration."""

from __future__ import annotations

from collections.abc import Callable
import logging
from typing import Any, final

from homeassistant.core import callback
from homeassistant.helpers.entity import Entity
import homeassistant.util.dt as dt_util

from .const import TAG_ID

_LOGGER = logging.getLogger(__name__)

LAST_SCANNED_BY_DEVICE_ID = "last_scanned_by_device_id"


class TagEntity(Entity):
    """Representation of a Tag entity."""

    _unrecorded_attributes = frozenset({TAG_ID})
    _attr_should_poll = False

    def __init__(
        self,
        entity_update_handlers: dict[str, Callable[[str | None, str | None], None]],
        name: str,
        tag_id: str,
        last_scanned: str | None,
        device_id: str | None,
    ) -> None:
        """Initialize the Tag event."""
        self._entity_update_handlers = entity_update_handlers
        self._attr_name = name
        self._tag_id = tag_id
        self._attr_unique_id = tag_id
        self._last_device_id: str | None = device_id
        self._last_scanned = last_scanned

    @callback
    def async_handle_event(
        self, device_id: str | None, last_scanned: str | None
    ) -> None:
        """Handle the Tag scan event."""
        if _LOGGER.isEnabledFor(logging.DEBUG):
            _LOGGER.debug(
                "Tag %s scanned by device %s at %s, last scanned at %s",
                self._tag_id,
                device_id,
                last_scanned,
                self._last_scanned,
            )
        self._last_device_id = device_id
        self._last_scanned = last_scanned
        self.async_write_ha_state()

    @property
    @final
    def state(self) -> str | None:
        """Return the entity state."""
        if (
            not self._last_scanned
            or (last_scanned := dt_util.parse_datetime(self._last_scanned)) is None
        ):
            return None
        return last_scanned.isoformat(timespec="milliseconds")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the sun."""
        return {TAG_ID: self._tag_id, LAST_SCANNED_BY_DEVICE_ID: self._last_device_id}

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()
        self._entity_update_handlers[self._tag_id] = self.async_handle_event

    async def async_will_remove_from_hass(self) -> None:
        """Handle entity being removed."""
        await super().async_will_remove_from_hass()
        del self._entity_update_handlers[self._tag_id]
