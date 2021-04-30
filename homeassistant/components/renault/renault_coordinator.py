"""Proxy to handle account communication with Renault servers."""
from __future__ import annotations

from collections.abc import Awaitable
from datetime import timedelta
import logging
from typing import Callable

from renault_api.kamereon.exceptions import (
    AccessDeniedException,
    KamereonResponseException,
    NotSupportedException,
)

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    T,
    UpdateFailed,
)


class RenaultDataUpdateCoordinator(DataUpdateCoordinator[T]):
    """Handle vehicle communication with Renault servers."""

    def __init__(
        self,
        hass: HomeAssistant,
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
            name=name,
            update_interval=update_interval,
            update_method=update_method,
        )
        self.access_denied = False
        self.not_supported = False

    async def _async_update_data(self) -> T:
        """Fetch the latest data from the source."""
        if self.update_method is None:
            raise NotImplementedError("Update method not implemented")
        try:
            return await self.update_method()
        except AccessDeniedException as err:
            # Disable because the account is not allowed to access this Renault endpoint.
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
            raise UpdateFailed(f"Error communicating with API: {err}") from err
