"""Coordinator for lookin devices."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import timedelta
import logging
import time
from typing import cast

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

NEVER_TIME = -120.0  # Time that will never match time.monotonic()


class LookinPushCoordinator:
    """Keep track of when the last push update was."""

    def __init__(self) -> None:
        """Init the push coordininator."""
        self.last_update = NEVER_TIME

    def update(self) -> None:
        """Remember the last push time."""
        self.last_update = time.monotonic()

    def is_active(self, interval: timedelta) -> bool:
        """Check if the last push update was recently."""
        time_since_last_update = time.monotonic() - self.last_update
        return time_since_last_update < interval.total_seconds()


class LookinDataUpdateCoordinator(DataUpdateCoordinator):
    """DataUpdateCoordinator to gather data for a specific lookin devices."""

    def __init__(
        self,
        hass: HomeAssistant,
        push_coordinator: LookinPushCoordinator,
        name: str,
        update_interval: timedelta | None = None,
        update_method: Callable[[], Awaitable[dict]] | None = None,
    ) -> None:
        """Initialize DataUpdateCoordinator to gather data for specific device."""
        self.push_coordinator = push_coordinator
        super().__init__(
            hass,
            _LOGGER,
            name=name,
            update_interval=update_interval,
            update_method=update_method,
        )

    @callback
    def async_set_updated_data(self, data: dict) -> None:
        """Manually update data, notify listeners and reset refresh interval, and remember."""
        self.push_coordinator.update()
        super().async_set_updated_data(data)

    async def _async_update_data(self) -> dict:
        """Fetch data if only if we have not been received a push inside the interval."""
        if self.update_interval is not None and self.push_coordinator.is_active(
            self.update_interval
        ):
            data = self.data
        else:
            data = await super()._async_update_data()
        return cast(dict, data)
