"""DataUpdateCoordinator for Wibeee energy monitors.

Handles both update modes:
- **Polling**: Periodically fetches status.xml (update_interval > 0).
- **Push**: Receives data via HTTP push (update_interval=None).
  Push data is injected via :meth:`async_push_update`.
  A staleness watchdog marks the coordinator as failed if no push arrives
  within ``stale_after``, so entities go unavailable instead of reporting
  stale last-known values.
"""

from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import Any
from xml.etree.ElementTree import ParseError as XMLParseError

import aiohttp
from pywibeee import WibeeeAPI

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)

# Type alias: phase_key -> sensor_key -> value
WibeeeData = dict[str, dict[str, Any]] | None


class WibeeeCoordinator(DataUpdateCoordinator[WibeeeData]):
    """Coordinator for Wibeee sensor data.

    In polling mode, ``_async_update_data`` fetches from the device API.
    In push mode, ``update_interval`` is None and data is injected
    externally via :meth:`async_push_update`.
    """

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        api: WibeeeAPI,
        *,
        config_entry: ConfigEntry,
        name: str | None = None,
        update_interval: timedelta | None = None,
        stale_after: timedelta | None = None,
    ) -> None:
        """Initialize the coordinator.

        ``stale_after`` enables a watchdog (push mode only): if no push
        data arrives within this interval, the coordinator is marked
        as failed and entities become unavailable.
        """
        self.api = api
        self._stale_after = stale_after
        self._stale_unsub: CALLBACK_TYPE | None = None

        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=name or f"Wibeee {api.host}",
            update_interval=update_interval,
        )

    async def _async_update_data(self) -> WibeeeData:
        """Fetch data from the Wibeee device (polling mode only)."""
        try:
            data = await self.api.async_fetch_sensors_data(retries=2)
        except (TimeoutError, aiohttp.ClientError, XMLParseError) as exc:
            _LOGGER.debug("Error fetching data from %s: %s", self.api.host, exc)
            raise UpdateFailed(
                f"Error fetching data from {self.api.host}: {exc}"
            ) from exc

        if data is None:
            raise UpdateFailed(f"No data received from Wibeee at {self.api.host}")

        if not isinstance(data, dict):
            raise UpdateFailed(
                f"Invalid data format from {self.api.host}: expected dict"
            )

        return data

    def async_push_update(self, data: WibeeeData) -> None:
        """Receive push data and update coordinator.

        This is the public API for push mode. The push receiver calls
        this method instead of ``async_set_updated_data`` directly,
        making the intent explicit and allowing future validation.
        """
        if not isinstance(data, dict):
            _LOGGER.warning(
                "Ignoring invalid push data for %s: expected dict, got %s",
                self.name,
                type(data).__name__,
            )
            return
        self.async_set_updated_data(data)
        self._reschedule_staleness_check()

    @callback
    def _reschedule_staleness_check(self) -> None:
        """(Re)arm the push staleness watchdog."""
        if self._stale_after is None:
            return
        if self._stale_unsub is not None:
            self._stale_unsub()
            self._stale_unsub = None
        self._stale_unsub = async_call_later(
            self.hass, self._stale_after, self._handle_stale_data
        )

    @callback
    def _handle_stale_data(self, _now: datetime) -> None:
        """Mark coordinator as failed when push data is stale."""
        self._stale_unsub = None
        message = (
            f"No push data received from {self.api.host} for "
            f"{self._stale_after}; marking sensors unavailable"
        )
        _LOGGER.warning(message)
        self.async_set_update_error(UpdateFailed(message))

    async def async_shutdown(self) -> None:
        """Cancel the staleness watchdog and shut down the coordinator."""
        if self._stale_unsub is not None:
            self._stale_unsub()
            self._stale_unsub = None
        await super().async_shutdown()
