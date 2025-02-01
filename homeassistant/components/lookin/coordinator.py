"""Coordinator for lookin devices."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import timedelta
import logging
import time

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import NEVER_TIME, POLLING_FALLBACK_SECONDS

_LOGGER = logging.getLogger(__name__)


class LookinPushCoordinator:
    """Keep track of when the last push update was."""

    def __init__(self, name: str) -> None:
        """Init the push coordininator."""
        self.last_update = NEVER_TIME
        self.name = name

    def update(self) -> None:
        """Remember the last push time."""
        self.last_update = time.monotonic()

    def active(self, interval: timedelta) -> bool:
        """Check if the last push update was recently."""
        time_since_last_update = time.monotonic() - self.last_update
        is_active = time_since_last_update < POLLING_FALLBACK_SECONDS
        _LOGGER.debug(
            "%s: push updates active: %s (time_since_last_update=%s)",
            self.name,
            is_active,
            time_since_last_update,
        )
        return is_active


class LookinDataUpdateCoordinator[_DataT](DataUpdateCoordinator[_DataT]):
    """DataUpdateCoordinator to gather data for a specific lookin devices."""

    def __init__(
        self,
        hass: HomeAssistant,
        push_coordinator: LookinPushCoordinator,
        name: str,
        update_interval: timedelta | None = None,
        update_method: Callable[[], Awaitable[_DataT]] | None = None,
    ) -> None:
        """Initialize DataUpdateCoordinator to gather data for specific device."""
        self.push_coordinator = push_coordinator
        super().__init__(
            hass,
            _LOGGER,
            name=name,
            update_interval=update_interval,
            update_method=update_method,
            always_update=False,
        )

    @callback
    def async_set_updated_data(self, data: _DataT) -> None:
        """Manually update data, notify listeners and reset refresh interval, and remember."""
        self.push_coordinator.update()
        super().async_set_updated_data(data)

    async def _async_update_data(self) -> _DataT:
        """Fetch data only if we have not received a push inside the interval."""
        interval = self.update_interval
        if (
            interval is not None
            and self.last_update_success
            and self.data
            and self.push_coordinator.active(interval)
        ):
            data = self.data
        else:
            data = await super()._async_update_data()
        return data
