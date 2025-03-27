"""Proxy to handle account communication with Renault servers."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import timedelta
import logging
from typing import TYPE_CHECKING, TypeVar

from renault_api.kamereon.exceptions import (
    AccessDeniedException,
    KamereonResponseException,
    NotSupportedException,
)
from renault_api.kamereon.models import KamereonVehicleDataAttributes

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

if TYPE_CHECKING:
    from . import RenaultConfigEntry
    from .renault_hub import RenaultHub

T = TypeVar("T", bound=KamereonVehicleDataAttributes)

# We have potentially 7 coordinators per vehicle
_PARALLEL_SEMAPHORE = asyncio.Semaphore(1)

LOGGER = logging.getLogger(__name__)


class RenaultDataUpdateCoordinator(DataUpdateCoordinator[T]):
    """Handle vehicle communication with Renault servers."""

    config_entry: RenaultConfigEntry
    update_method: Callable[[], Awaitable[T]]

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: RenaultConfigEntry,
        hub: RenaultHub,
        logger: logging.Logger,
        *,
        name: str,
        update_interval: timedelta,
        update_method: Callable[[], Awaitable[T]],
    ) -> None:
        """Initialise coordinator."""
        super().__init__(
            hass,
            logger,
            config_entry=config_entry,
            name=name,
            update_interval=update_interval,
            update_method=update_method,
        )
        self.access_denied = False
        self.not_supported = False
        self._has_already_worked = False
        self._hub = hub

    async def _async_update_data(self) -> T:
        """Fetch the latest data from the source."""

        if self._hub.check_throttled():
            LOGGER.warning("API throttled: Waiting for next scan")
            return self.data

        wait_seconds = self._hub.get_wait_time_for_next_call()
        if wait_seconds > 0:
            # we have called the API too many times, wait before calling again ... or simply wait for the next update, self.data?
            if (
                self.update_interval is not None
                and 2 * wait_seconds > self.update_interval.total_seconds()
            ):
                # too many calls ... wait for next scan, do as if data hasn't changed
                return self.data
            await asyncio.sleep(2 * wait_seconds)

        try:
            async with _PARALLEL_SEMAPHORE:
                self._hub.add_api_call()
                data = await self.update_method()

        except AccessDeniedException as err:
            # This can mean both a temporary error or a permanent error. If it has
            # worked before, make it temporary, if not disable the update interval.
            if not self._has_already_worked:
                self.update_interval = None
                self.access_denied = True
            raise UpdateFailed(f"This endpoint is denied: {err}") from err

        except NotSupportedException as err:
            # Disable because the vehicle does not support this Renault endpoint.
            self.update_interval = None
            self.not_supported = True
            raise UpdateFailed(f"This endpoint is not supported: {err}") from err

        except KamereonResponseException as err:
            # Other Renault errors.
            # in case of quotas limits, we should not raise an exception? At minimum be sure of a proper cooldown for the API
            # Error communicating with API: ('err.func.wired.overloaded', 'You have reached your quota limit')
            if err.error_code == "err.func.wired.overloaded":
                # ok we do have a throttling at API level ... we should wait a lot for the next update to be called?
                self._hub.got_throttled()
                LOGGER.warning("API throttled")
                if self._has_already_worked:
                    return self.data

            raise UpdateFailed(f"Error communicating with API: {err}") from err

        self._has_already_worked = True
        return data

    async def async_config_entry_first_refresh(self) -> None:
        """Refresh data for the first time when a config entry is setup.

        Contrary to base implementation, we are not raising ConfigEntryNotReady
        but only updating the `access_denied` and `not_supported` flags.
        """
        await self._async_refresh(log_failures=False, raise_on_auth_failed=True)
