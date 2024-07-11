"""Define an update coordinator for OpenUV."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, cast

from pyopenuv.errors import InvalidApiKeyError, OpenUvError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import LOGGER

DEFAULT_DEBOUNCER_COOLDOWN_SECONDS = 15 * 60


class OpenUvCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Define an OpenUV data coordinator."""

    config_entry: ConfigEntry
    update_method: Callable[[], Awaitable[dict[str, Any]]]

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        entry: ConfigEntry,
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

        self._entry = entry
        self.latitude = latitude
        self.longitude = longitude

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from OpenUV."""
        try:
            data = await self.update_method()
        except InvalidApiKeyError as err:
            raise ConfigEntryAuthFailed("Invalid API key") from err
        except OpenUvError as err:
            raise UpdateFailed(str(err)) from err

        return cast(dict[str, Any], data["result"])
