"""Define an update coordinator for OpenUV."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
import datetime as dt
from typing import Any, cast

from pyopenuv.errors import InvalidApiKeyError, OpenUvError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import event as evt
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util.dt import parse_datetime, utcnow

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
            config_entry=entry,
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
        except InvalidApiKeyError as err:
            raise ConfigEntryAuthFailed("Invalid API key") from err
        except OpenUvError as err:
            raise UpdateFailed(str(err)) from err

        return cast(dict[str, Any], data["result"])


class OpenUvProtectionWindowCoordinator(OpenUvCoordinator):
    """Define an OpenUV data coordinator for the protection window."""

    _reprocess_listener: CALLBACK_TYPE | None = None

    async def _async_update_data(self) -> dict[str, Any]:
        data = await super()._async_update_data()

        for key in ("from_time", "to_time", "from_uv", "to_uv"):
            # a key missing from the data is an error.
            if key not in data:
                msg = f"Update failed due to missing data: {key}"
                raise UpdateFailed(msg)

            # check for null or zero value in the data & skip further processing
            # of this update if one is found. this is a normal condition
            # indicating that there is no protection window.
            if not data[key]:
                LOGGER.warning("Skipping update due to missing data: %s", key)
                return {}

        data = self._parse_data(data)
        data = self._process_data(data)

        self._schedule_reprocessing(data)

        return data

    def _parse_data(self, data: dict[str, Any]) -> dict[str, Any]:
        """Parse & update datetime values in data."""

        from_dt = parse_datetime(data["from_time"])
        to_dt = parse_datetime(data["to_time"])

        if not from_dt or not to_dt:
            LOGGER.warning(
                "Unable to parse protection window datetimes: %s, %s",
                data["from_time"],
                data["to_time"],
            )
            return {}

        return {**data, "from_time": from_dt, "to_time": to_dt}

    def _process_data(self, data: dict[str, Any]) -> dict[str, Any]:
        """Process data for consumption by entities.

        Adds the `is_on` key to the resulting data.
        """
        if not {"from_time", "to_time"}.issubset(data):
            return {}

        return {**data, "is_on": data["from_time"] <= utcnow() <= data["to_time"]}

    def _schedule_reprocessing(self, data: dict[str, Any]) -> None:
        """Schedule reprocessing of data."""

        if not {"from_time", "to_time"}.issubset(data):
            return

        now = utcnow()
        from_dt = data["from_time"]
        to_dt = data["to_time"]
        reprocess_at: dt.datetime | None = None

        if from_dt and from_dt > now:
            reprocess_at = from_dt
        if to_dt and to_dt > now:
            reprocess_at = to_dt if not reprocess_at else min(to_dt, reprocess_at)

        if reprocess_at:
            self._async_cancel_reprocess_listener()
            self._reprocess_listener = evt.async_track_point_in_utc_time(
                self.hass,
                self._async_handle_reprocess_event,
                reprocess_at,
            )

    def _async_cancel_reprocess_listener(self) -> None:
        """Cancel the reprocess event listener."""
        if self._reprocess_listener:
            self._reprocess_listener()
            self._reprocess_listener = None

    @callback
    def _async_handle_reprocess_event(self, now: dt.datetime) -> None:
        """Timer callback for reprocessing the data & updating listeners."""
        self._async_cancel_reprocess_listener()

        self.data = self._process_data(self.data)
        self._schedule_reprocessing(self.data)

        self.async_update_listeners()
