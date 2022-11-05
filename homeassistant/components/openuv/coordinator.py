"""Define an update coordinator for OpenUV."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, cast

from pyopenuv.errors import OpenUvError

from homeassistant.core import HomeAssistant
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import LOGGER

DEFAULT_DEBOUNCER_COOLDOWN_SECONDS = 15 * 60


class OpenUvCoordinator(DataUpdateCoordinator):
    """Define an OpenUV data coordinator."""

    update_method: Callable[[], Awaitable[dict[str, Any]]]

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        name: str,
        latitude: str,
        longitude: str,
        update_method: Callable[[], Awaitable[dict[str, Any]]],
    ) -> None:
        """Initialize."""
        super().__init__(
            hass,
            LOGGER,
            name=name,
            update_method=update_method,
            request_refresh_debouncer=Debouncer(
                hass,
                LOGGER,
                cooldown=DEFAULT_DEBOUNCER_COOLDOWN_SECONDS,
                immediate=True,
            ),
        )

        self.latitude = latitude
        self.longitude = longitude

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from OpenUV."""
        try:
            data = await self.update_method()
        except OpenUvError as err:
            raise UpdateFailed(f"Error during protection data update: {err}") from err
        return cast(dict[str, Any], data["result"])
