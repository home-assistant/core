"""Cover support for OpenGarage."""

from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
from typing import Any, cast, override

from homeassistant.components.cover import (
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
    CoverState,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import OpenGarageConfigEntry, OpenGarageDataUpdateCoordinator
from .entity import OpenGarageEntity

# Legacy firmware reports only the endpoints, including during travel and alarms.
MOVEMENT_TIMEOUT = timedelta(seconds=60)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OpenGarageConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the OpenGarage cover."""
    async_add_entities(
        [OpenGarageCover(entry.runtime_data, cast(str, entry.unique_id))]
    )


class OpenGarageCover(OpenGarageEntity, CoverEntity):
    """Representation of an OpenGarage cover."""

    _attr_device_class = CoverDeviceClass.GARAGE
    _attr_supported_features = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE
    _attr_name = None

    def __init__(
        self, coordinator: OpenGarageDataUpdateCoordinator, device_id: str
    ) -> None:
        """Initialize the cover."""
        self._state = "unknown"
        self._state_before_move = "unknown"
        self._movement_deadline: datetime | None = None
        super().__init__(coordinator, device_id)

    @property
    @override
    def is_closed(self) -> bool | None:
        """Return whether the cover is closed."""
        if self._state == "unknown":
            return None
        return self._state == CoverState.CLOSED

    @property
    @override
    def is_closing(self) -> bool:
        """Return whether the cover is closing."""
        return self._state == CoverState.CLOSING

    @property
    @override
    def is_opening(self) -> bool:
        """Return whether the cover is opening."""
        return self._state == CoverState.OPENING

    @property
    @override
    def current_cover_position(self) -> int | None:
        """Return an endpoint position when known."""
        if self._state == CoverState.CLOSED:
            return 0
        if self._state == CoverState.OPEN:
            return 100
        return None

    @override
    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        if self._state in (CoverState.CLOSED, CoverState.CLOSING):
            return
        await self._async_move(
            CoverState.CLOSING,
            self.coordinator.open_garage_connection.push_close_button,
        )

    @override
    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        if self._state in (CoverState.OPEN, CoverState.OPENING):
            return
        await self._async_move(
            CoverState.OPENING, self.coordinator.open_garage_connection.push_open_button
        )

    @override
    async def async_toggle(self, **kwargs: Any) -> None:
        """Choose direction from the current state."""
        if self._state in (CoverState.CLOSED, CoverState.CLOSING):
            await self.async_open_cover(**kwargs)
        else:
            await self.async_close_cover(**kwargs)

    async def _async_move(
        self, state: CoverState, command: Callable[[], Awaitable[int | None]]
    ) -> None:
        """Send a directional command and track its pending state."""
        self._state_before_move = self.coordinator.data.door_state
        self._movement_deadline = dt_util.utcnow() + MOVEMENT_TIMEOUT
        self._state = state
        self.async_write_ha_state()
        try:
            await self.coordinator.async_command(command)
        except HomeAssistantError:
            self._movement_deadline = None
            self._state = self.coordinator.data.door_state
            self.async_write_ha_state()
            raise

    @callback
    @override
    def _update_attr(self) -> None:
        """Reconcile reported state with a pending command."""
        state = self.coordinator.data.door_state
        if (
            self._movement_deadline is not None
            and dt_util.utcnow() < self._movement_deadline
            and state == self._state_before_move
        ):
            return
        self._movement_deadline = None
        self._state = state
