"""Platform for the opengarage.io cover component."""

from __future__ import annotations

import logging
from typing import Any, cast

from homeassistant.components.cover import (
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
    CoverState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import OpenGarageDataUpdateCoordinator
from .entity import OpenGarageEntity

_LOGGER = logging.getLogger(__name__)

STATES_MAP = {0: CoverState.CLOSED, 1: CoverState.OPEN}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the OpenGarage covers."""
    async_add_entities(
        [OpenGarageCover(hass.data[DOMAIN][entry.entry_id], cast(str, entry.unique_id))]
    )


class OpenGarageCover(OpenGarageEntity, CoverEntity):
    """Representation of a OpenGarage cover."""

    _attr_device_class = CoverDeviceClass.GARAGE
    _attr_supported_features = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE
    _attr_name = None

    def __init__(
        self, coordinator: OpenGarageDataUpdateCoordinator, device_id: str
    ) -> None:
        """Initialize the cover."""
        self._state: str | None = None
        self._state_before_move: str | None = None

        super().__init__(coordinator, device_id)

    @property
    def is_closed(self) -> bool | None:
        """Return if the cover is closed."""
        if self._state is None:
            return None
        return self._state == CoverState.CLOSED

    @property
    def is_closing(self) -> bool | None:
        """Return if the cover is closing."""
        if self._state is None:
            return None
        return self._state == CoverState.CLOSING

    @property
    def is_opening(self) -> bool | None:
        """Return if the cover is opening."""
        if self._state is None:
            return None
        return self._state == CoverState.OPENING

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        if self._state in [CoverState.CLOSED, CoverState.CLOSING]:
            return
        self._state_before_move = self._state
        self._state = CoverState.CLOSING
        await self._push_button()

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        if self._state in [CoverState.OPEN, CoverState.OPENING]:
            return
        self._state_before_move = self._state
        self._state = CoverState.OPENING
        await self._push_button()

    @callback
    def _update_attr(self) -> None:
        """Update the state and attributes."""
        status = self.coordinator.data

        state = STATES_MAP.get(status.get("door"))  # type: ignore[arg-type]
        if self._state_before_move is not None:
            if self._state_before_move != state:
                self._state = state
                self._state_before_move = None
        else:
            self._state = state

    async def _push_button(self):
        """Send commands to API."""
        result = await self.coordinator.open_garage_connection.push_button()
        if result is None:
            _LOGGER.error("Unable to connect to OpenGarage device")
        if result == 1:
            return

        if result == 2:
            _LOGGER.error("Unable to control %s: Device key is incorrect", self.name)
        elif result > 2:
            _LOGGER.error("Unable to control %s: Error code %s", self.name, result)

        self._state = self._state_before_move
        self._state_before_move = None
