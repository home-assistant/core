"""Constants for the solax integration."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, override

from solax import InverterResponse, RealTimeAPI
from solax.inverter import InverterError

from homeassistant.core import CALLBACK_TYPE, callback
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import DOMAIN


@dataclass(slots=True)
class Reset:
    """Daily reset event."""

    start_of_local_day: datetime


type SolaxDataUpdate = InverterResponse | Reset


class SolaxDataUpdateCoordinator(DataUpdateCoordinator[SolaxDataUpdate]):
    """DataUpdateCoordinator for solax."""

    def __init__(self, api: RealTimeAPI, *args, **kwargs) -> None:
        """Initialize DataUpdateCoordinator."""

        super().__init__(*args, **kwargs)
        self.api = api

    _untrack_midnight: CALLBACK_TYPE | None = None

    @override
    async def _async_update_data(self) -> SolaxDataUpdate:
        try:
            return await self.api.get_data()
        except InverterError as err:
            raise UpdateFailed from err

    @callback
    def async_listen_for_midnight(self, today: datetime) -> None:
        """Reset at start of local day."""
        self.async_set_updated_data(
            Reset(start_of_local_day=dt_util.start_of_local_day(today))
        )

    @override
    @callback
    def async_add_listener(
        self, update_callback: CALLBACK_TYPE, context: Any = None
    ) -> Callable[[], None]:
        title_or_domain = (
            self.config_entry.title if self.config_entry is not None else DOMAIN
        )
        if not self._listeners:
            self.logger.debug("start tracking midnight for %s", title_or_domain)
            self._untrack_midnight = async_track_time_change(
                hass=self.hass,
                action=self.async_listen_for_midnight,
                hour=0,
                minute=0,
                second=0,
            )

        remove_listener = super().async_add_listener(
            update_callback=update_callback, context=context
        )

        @callback
        def wrap_remove_listener() -> None:
            self._listeners[remove_listener] = self._listeners.pop(wrap_remove_listener)
            remove_listener()
            if not self._listeners and self._untrack_midnight:
                self.logger.debug("stop tracking midnight for %s", title_or_domain)
                self._untrack_midnight()
                self._untrack_midnight = None

        self._listeners[wrap_remove_listener] = self._listeners.pop(remove_listener)

        return wrap_remove_listener
