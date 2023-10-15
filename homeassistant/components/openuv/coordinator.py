"""Define an update coordinator for OpenUV."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
from typing import Any, cast

from pyopenuv import Client
from pyopenuv.errors import InvalidApiKeyError, OpenUvError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.event import async_track_utc_time_change
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_FROM_WINDOW,
    CONF_TO_WINDOW,
    DATA_PROTECTION_WINDOW,
    DATA_UV,
    DEFAULT_FROM_WINDOW,
    DEFAULT_TO_WINDOW,
    LOGGER,
)

DEFAULT_DEBOUNCER_COOLDOWN_SECONDS = 15 * 60


class OpenUvCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Define an OpenUV data coordinator."""

    config_entry: ConfigEntry
    update_method: Callable[[], Awaitable[dict[str, Any]]]

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: Client,
        *,
        name: str,
        update_interval: timedelta | None = None,
    ) -> None:
        """Initialize."""
        super().__init__(
            hass,
            LOGGER,
            name=name,
            update_interval=update_interval,
            request_refresh_debouncer=Debouncer(
                hass,
                LOGGER,
                cooldown=DEFAULT_DEBOUNCER_COOLDOWN_SECONDS,
                immediate=True,
            ),
        )

        self._client = client
        self._entry = entry
        self.latitude = client.latitude
        self.longitude = client.longitude


class ProtectionWindowCoordinator(OpenUvCoordinator):
    """Define an OpenUV data coordinator for protection window data."""

    DATA_KEYS = ("from_time", "to_time")

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: Client) -> None:
        """Initialize."""
        super().__init__(
            hass,
            entry,
            client,
            name=DATA_PROTECTION_WINDOW,
            update_interval=timedelta(minutes=30),
        )

        self.window_calculated: bool = False

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from OpenUV."""
        if self.window_calculated:
            # If the window has already been calculated, return the existing data
            # (which, by default, won't call listeners) and save an API call:
            return self.data

        low = self._entry.options.get(CONF_FROM_WINDOW, DEFAULT_FROM_WINDOW)
        high = self._entry.options.get(CONF_TO_WINDOW, DEFAULT_TO_WINDOW)

        try:
            data = await self._client.uv_protection_window(low=low, high=high)
        except InvalidApiKeyError as err:
            raise ConfigEntryAuthFailed("Invalid API key") from err
        except OpenUvError as err:
            raise UpdateFailed(str(err)) from err

        data = data["result"]

        if all(key in data for key in self.DATA_KEYS):
            # The OpenUV API can sometimes return a successful response that's missing
            # the protection window data; if the appropriate keys exist, mark the data
            # as valid:
            self.window_calculated = True

        return data

    async def async_config_entry_first_refresh(self) -> None:
        """Refresh data for the first time when a config entry is setup."""

        @callback
        def async_reset_window_check(_: datetime) -> None:
            """Reset the flag that indicates if the window has been calculated."""
            self.window_calculated = False

        self._entry.async_on_unload(
            # Reset the flag that indicates if the window has been calculated at
            # midnight every day:
            async_track_utc_time_change(
                self.hass,
                async_reset_window_check,
                hour=0,
                minute=0,
                second=0,
                local=True,
            )
        )

        await super().async_config_entry_first_refresh()


class UvIndexCoordinator(OpenUvCoordinator):
    """Define an OpenUV data coordinator for UV data."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: Client) -> None:
        """Initialize."""
        super().__init__(hass, entry, client, name=DATA_UV)

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from OpenUV."""
        try:
            data = await self._client.uv_index()
        except InvalidApiKeyError as err:
            raise ConfigEntryAuthFailed("Invalid API key") from err
        except OpenUvError as err:
            raise UpdateFailed(str(err)) from err

        return cast(dict[str, Any], data["result"])
