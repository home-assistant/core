"""DataUpdateCoordinator for Wibeee energy monitors.

Handles both update modes:
- **Polling**: Periodically fetches status.xml (update_interval > 0).
- **Push**: Receives data via HTTP push (update_interval=None).
  Push data is injected via :meth:`async_push_update`.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Mapping
from datetime import timedelta
from xml.etree.ElementTree import ParseError as XMLParseError

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .api import WibeeeAPI

_LOGGER = logging.getLogger(__name__)

# Type alias: phase_key -> sensor_key -> value
WibeeeData = Mapping[str, Mapping[str, str]]


class WibeeeCoordinator(DataUpdateCoordinator[WibeeeData]):
    """Coordinator for Wibeee sensor data.

    In polling mode, ``_async_update_data`` fetches from the device API.
    In push mode, ``update_interval`` is None and data is injected
    externally via :meth:`async_push_update`.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        api: WibeeeAPI,
        *,
        name: str | None = None,
        update_interval: timedelta | None = None,
    ) -> None:
        """Initialize the coordinator."""
        self.api = api

        super().__init__(
            hass,
            _LOGGER,
            name=name or f"Wibeee {api.host}",
            update_interval=update_interval,
        )

    async def _async_update_data(self) -> WibeeeData:
        """Fetch data from the Wibeee device (polling mode only)."""
        try:
            data = await self.api.async_fetch_sensors_data(retries=2)
        except (aiohttp.ClientError, asyncio.TimeoutError, XMLParseError) as exc:
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
