"""Rabbit Air Update Coordinator."""

from collections.abc import Coroutine
from datetime import timedelta
import logging
from typing import Any, cast

from rabbitair import Client, State

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


class RabbitAirDebouncer(Debouncer[Coroutine[Any, Any, None]]):
    """Class to rate limit calls to a specific command."""

    def __init__(
        self,
        hass: HomeAssistant,
    ) -> None:
        """Initialize debounce."""
        # We don't want an immediate refresh since the device needs some time
        # to apply the changes and reflect the updated state. Two seconds
        # should be sufficient, since the internal cycle of the device runs at
        # one-second intervals.
        super().__init__(hass, _LOGGER, cooldown=2.0, immediate=False)

    async def async_call(self) -> None:
        """Call the function."""
        # Restart the timer.
        self.async_cancel()
        await super().async_call()

    def has_pending_call(self) -> bool:
        """Indicate that the debouncer has a call waiting for cooldown."""
        return self._execute_at_end_of_timer


class RabbitAirDataUpdateCoordinator(DataUpdateCoordinator[State]):
    """Class to manage fetching data from single endpoint."""

    config_entry: ConfigEntry

    def __init__(
        self, hass: HomeAssistant, config_entry: ConfigEntry, device: Client
    ) -> None:
        """Initialize global data updater."""
        self.device = device
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name="rabbitair",
            update_interval=timedelta(seconds=10),
            request_refresh_debouncer=RabbitAirDebouncer(hass),
        )

    async def _async_update_data(self) -> State:
        return await self.device.get_state()

    async def _async_refresh(
        self,
        log_failures: bool = True,
        raise_on_auth_failed: bool = False,
        scheduled: bool = False,
        raise_on_entry_error: bool = False,
    ) -> None:
        """Refresh data."""

        # Skip a scheduled refresh if there is a pending requested refresh.
        debouncer = cast(RabbitAirDebouncer, self._debounced_refresh)
        if scheduled and debouncer.has_pending_call():
            return

        await super()._async_refresh(
            log_failures, raise_on_auth_failed, scheduled, raise_on_entry_error
        )
