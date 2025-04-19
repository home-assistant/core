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
    QuotaLimitException,
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
        self.assumed_state = False

        self._has_already_worked = False
        self._hub = hub

    async def _async_update_data(self) -> T:
        """Fetch the latest data from the source."""

        if self._hub.is_throttled():
            if not self._has_already_worked:
                raise UpdateFailed("Renault hub currently throttled: init skipped")
            # we have been throttled and decided to cooldown
            # so do not count this update as an error
            # coordinator. last_update_success should still be ok
            self.logger.debug("Renault hub currently throttled: scan skipped")
            self.assumed_state = True
            return self.data

        try:
            async with _PARALLEL_SEMAPHORE:
                data = await self.update_method()

        except AccessDeniedException as err:
            # This can mean both a temporary error or a permanent error. If it has
            # worked before, make it temporary, if not disable the update interval.
            if not self._has_already_worked:
                self.update_interval = None
                self.access_denied = True
            raise UpdateFailed(f"This endpoint is denied: {err}") from err

        except QuotaLimitException as err:
            # The data we got is not bad per see, initiate cooldown for all coordinators
            self._hub.set_throttled()
            if self._has_already_worked:
                self.assumed_state = True
                self.logger.warning("Renault API throttled")
                return self.data

            raise UpdateFailed(f"Renault API throttled: {err}") from err

        except NotSupportedException as err:
            # Disable because the vehicle does not support this Renault endpoint.
            self.update_interval = None
            self.not_supported = True
            raise UpdateFailed(f"This endpoint is not supported: {err}") from err

        except KamereonResponseException as err:
            # Other Renault errors.
            raise UpdateFailed(f"Error communicating with API: {err}") from err

        self._has_already_worked = True
        self.assumed_state = False
        return data

    async def async_config_entry_first_refresh(self) -> None:
        """Refresh data for the first time when a config entry is setup.

        Contrary to base implementation, we are not raising ConfigEntryNotReady
        but only updating the `access_denied` and `not_supported` flags.
        """
        await self._async_refresh(log_failures=False, raise_on_auth_failed=True)
