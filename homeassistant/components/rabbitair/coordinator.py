"""Rabbit Air Update Coordinator."""
from typing import cast

from rabbitair import State

from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator


class RabbitAirDebouncer(Debouncer):
    """Class to rate limit calls to a specific command."""

    async def async_call(self) -> None:
        """Call the function."""

        # Restart the timer.
        self.async_cancel()
        await super().async_call()

    def is_cooling_down(self) -> bool:
        """Indicate that the debouncer is waiting for cooldown."""
        return self._timer_task is not None


class RabbitAirDataUpdateCoordinator(DataUpdateCoordinator[State]):
    """Class to manage fetching data from single endpoint."""

    async def _async_refresh(
        self,
        log_failures: bool = True,
        raise_on_auth_failed: bool = False,
        scheduled: bool = False,
    ) -> None:
        """Refresh data."""

        # Skip a scheduled refresh if there is a pending requested refresh.
        debouncer = cast(RabbitAirDebouncer, self._debounced_refresh)
        if scheduled and debouncer.is_cooling_down():
            return

        await super()._async_refresh(log_failures, raise_on_auth_failed, scheduled)
