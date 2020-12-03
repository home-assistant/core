"""Proxy to handle account communication with Renault servers."""
from typing import Optional

from renault_api.kamereon.exceptions import (
    AccessDeniedException,
    KamereonResponseException,
    NotSupportedException,
)

from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    T,
    UpdateFailed,
)


class RenaultDataUpdateCoordinator(DataUpdateCoordinator):
    """Handle vehicle communication with Renault servers."""

    def __init__(self, *args, **kwargs) -> None:
        """Initialise coordinator."""
        super().__init__(*args, **kwargs)
        self.access_denied = False
        self.not_supported = False

    async def _async_update_data(self) -> Optional[T]:
        """Fetch the latest data from the source."""
        if self.update_method is None:
            raise NotImplementedError("Update method not implemented")
        try:
            return await self.update_method()
        except AccessDeniedException as err:
            # Disable because the account is not allowed to access this Renault endpoint.
            self.update_interval = None
            self.access_denied = True
            raise UpdateFailed(f"This endpoint has been disabled: {err}") from err

        except NotSupportedException as err:
            # Disable because the vehicle does not support this Renault endpoint.
            self.update_interval = None
            self.not_supported = True
            raise UpdateFailed(f"This endpoint has been disabled: {err}") from err

        except KamereonResponseException as err:
            # Other Renault errors.
            raise UpdateFailed(f"Error communicating with API: {err}") from err
