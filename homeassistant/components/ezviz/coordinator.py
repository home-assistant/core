"""Provides the ezviz DataUpdateCoordinator."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import Any

from pyezvizapi.client import EzvizClient
from pyezvizapi.exceptions import (
    EzvizAuthTokenExpired,
    EzvizAuthVerificationCode,
    HTTPError,
    InvalidURL,
    PyEzvizError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

type EzvizConfigEntry = ConfigEntry[EzvizDataUpdateCoordinator]


class EzvizDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching EZVIZ data."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: EzvizConfigEntry,
        *,
        api: EzvizClient,
        api_timeout: int,
        scan_interval: int = DEFAULT_SCAN_INTERVAL,
    ) -> None:
        """Initialize global EZVIZ data updater."""
        self.ezviz_client = api
        self._api_timeout = api_timeout
        self._mqtt_started = False
        self._default_interval = timedelta(seconds=scan_interval)
        self._burst_restore_task: asyncio.Task | None = None

        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=self._default_interval,
        )

    async def set_burst_interval(
        self, interval_seconds: int, duration_seconds: int
    ) -> None:
        """Temporarily set a fast polling interval, then restore the default."""
        if self._burst_restore_task and not self._burst_restore_task.done():
            self._burst_restore_task.cancel()

        self.update_interval = timedelta(seconds=interval_seconds)
        _LOGGER.info(
            "EZVIZ burst polling: %ds for %ds", interval_seconds, duration_seconds
        )
        await self.async_request_refresh()
        self._burst_restore_task = self.hass.async_create_task(
            self._restore_interval_after(duration_seconds)
        )

    async def _restore_interval_after(self, duration_seconds: int) -> None:
        """Wait then restore the default polling interval."""
        try:
            await asyncio.sleep(duration_seconds)
        except asyncio.CancelledError:
            return
        self.update_interval = self._default_interval
        _LOGGER.info(
            "EZVIZ burst polling ended, restored to %ss", self._default_interval
        )

    async def start_mqtt(self) -> None:
        """Start the EZVIZ MQTT push listener in the background."""
        if self._mqtt_started:
            return
        try:
            await self.hass.async_add_executor_job(self._setup_mqtt)
            self._mqtt_started = True
            _LOGGER.debug("EZVIZ MQTT push listener started")
        except Exception:
            _LOGGER.warning(
                "Could not start EZVIZ MQTT push listener, "
                "falling back to polling only",
                exc_info=True,
            )

    def _setup_mqtt(self) -> None:
        """Set up and connect the MQTT client (runs in executor)."""
        mqtt_client = self.ezviz_client.get_mqtt_client(
            on_message_callback=self._on_mqtt_message,
        )
        mqtt_client.connect(clean_session=True)

    def _on_mqtt_message(self, message: dict[str, Any]) -> None:
        """Handle incoming MQTT push and request a coordinator refresh."""
        ext = message.get("ext", {}) if isinstance(message.get("ext"), dict) else {}
        device_serial = ext.get("device_serial", "unknown")
        _LOGGER.debug("MQTT push received for %s, requesting refresh", device_serial)
        self.hass.loop.call_soon_threadsafe(
            self.hass.async_create_task,
            self.async_request_refresh(),
        )

    async def stop_mqtt(self) -> None:
        """Stop the MQTT push listener."""
        if not self._mqtt_started:
            return
        try:
            mqtt_client = self.ezviz_client.mqtt_client
            if mqtt_client:
                await self.hass.async_add_executor_job(mqtt_client.stop)
            self._mqtt_started = False
            _LOGGER.debug("EZVIZ MQTT push listener stopped")
        except Exception:
            _LOGGER.debug("Error stopping MQTT listener", exc_info=True)

    async def _async_update_data(self) -> dict:
        """Fetch data from EZVIZ."""
        try:
            async with asyncio.timeout(self._api_timeout):
                return await self.hass.async_add_executor_job(
                    self.ezviz_client.load_devices
                )

        except (EzvizAuthTokenExpired, EzvizAuthVerificationCode) as error:
            raise ConfigEntryAuthFailed from error

        except (InvalidURL, HTTPError, PyEzvizError) as error:
            raise UpdateFailed(f"Invalid response from API: {error}") from error
