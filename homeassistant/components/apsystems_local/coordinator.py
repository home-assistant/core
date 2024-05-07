"""The coordinator for APsystems local API integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from time import monotonic

from aiohttp import client_exceptions
from APsystemsEZ1 import APsystemsEZ1M, ReturnOutputData

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


class InverterNotAvailable(Exception):
    """Error used when Device is offline."""


class ApSystemsDataCoordinator(DataUpdateCoordinator):
    """Coordinator used for all sensors."""

    def __init__(self, hass: HomeAssistant, api: APsystemsEZ1M) -> None:
        """Initialize my coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            # Name of the data. For logging purposes.
            name="APSystems Data",
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=timedelta(seconds=12),
        )
        self.api = api
        self.always_update = True

    async def _async_update_data(self) -> ReturnOutputData | None:  # type: ignore[override]
        try:
            return await self.api.get_output_data()
        except (TimeoutError, client_exceptions.ClientConnectionError):
            # raise InverterNotAvailable
            raise InverterNotAvailable from None

    async def _async_refresh(  # noqa: C901
        self,
        log_failures: bool = True,
        raise_on_auth_failed: bool = False,
        scheduled: bool = False,
        raise_on_entry_error: bool = False,
    ) -> None:
        self._async_unsub_refresh()
        self._debounced_refresh.async_cancel()
        if self._shutdown_requested or scheduled and self.hass.is_stopping:
            return

        if log_timing := self.logger.isEnabledFor(logging.DEBUG):
            start = monotonic()

        auth_failed = False
        previous_update_success = self.last_update_success
        previous_data = self.data
        exc_triggered = False
        try:
            self.data = await self._async_update_data()  # type: ignore[assignment]
        except InverterNotAvailable:
            self.last_update_success = False
            exc_triggered = True
        except Exception as err:  # pylint: disable=broad-except
            self.last_exception = err
            self.last_update_success = False
            self.logger.exception("Unexpected error fetching %s data", self.name)
            exc_triggered = True
        else:
            if not self.last_update_success and not exc_triggered:
                self.last_update_success = True
                self.logger.info("Fetching %s data recovered", self.name)
        finally:
            if log_timing:
                self.logger.debug(
                    "Finished fetching %s data in %.3f seconds (success: %s)",
                    self.name,
                    monotonic() - start,
                    self.last_update_success,
                )
            if not auth_failed and self._listeners and not self.hass.is_stopping:
                self._schedule_refresh()
        if not self.last_update_success and not previous_update_success:
            return
        if (
            self.always_update
            or self.last_update_success != previous_update_success
            or previous_data != self.data
        ):
            self.async_update_listeners()
