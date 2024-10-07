"""Support for covers connected with WMS WebControl pro."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from wmspro.const import (
    WMS_WebControl_pro_API_actionDescription,
    WMS_WebControl_pro_API_actionType,
)

from homeassistant.components.cover import ATTR_POSITION, CoverDeviceClass, CoverEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import WebControlProConfigEntry
from .entity import WebControlProGenericEntity

SCAN_INTERVAL = timedelta(seconds=5)
PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: WebControlProConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the WMS based covers from a config entry."""
    hub = config_entry.runtime_data

    entities: list[WebControlProGenericEntity] = []
    for dest in hub.dests.values():
        if dest.action(WMS_WebControl_pro_API_actionDescription.AwningDrive):
            entities.append(WebControlProAwning(config_entry.entry_id, dest))  # noqa: PERF401

    async_add_entities(entities)


class WebControlProAwning(WebControlProGenericEntity, CoverEntity):
    """Representation of a WMS based awning."""

    _attr_device_class = CoverDeviceClass.AWNING

    @property
    def current_cover_position(self) -> int | None:
        """Return current position of cover."""
        action = self._dest.action(WMS_WebControl_pro_API_actionDescription.AwningDrive)
        return action["percentage"]

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        action = self._dest.action(WMS_WebControl_pro_API_actionDescription.AwningDrive)
        await action(percentage=kwargs[ATTR_POSITION])

    @property
    def is_closed(self) -> bool | None:
        """Return if the cover is closed."""
        return self.current_cover_position == 0

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        action = self._dest.action(WMS_WebControl_pro_API_actionDescription.AwningDrive)
        await action(percentage=100)

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        action = self._dest.action(WMS_WebControl_pro_API_actionDescription.AwningDrive)
        await action(percentage=0)

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the device if in motion."""
        action = self._dest.action(
            WMS_WebControl_pro_API_actionDescription.ManualCommand,
            WMS_WebControl_pro_API_actionType.Stop,
        )
        await action()
