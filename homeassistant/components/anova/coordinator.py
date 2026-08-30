"""Support for Anova Coordinators."""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging
from typing import override

from anova_wifi import (
    AnovaApi,
    APCUpdate,
    APCWifiDevice,
    InvalidLogin,
    NoDevicesFound,
    WebsocketFailure,
)
from anova_wifi.exceptions import LoginUnreachable

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

RECONNECT_RETRY_DELAY = 60
MAX_RECONNECT_BACKOFF = timedelta(minutes=15)

# Anova's protocol has no offline/disconnect signal for a device that's still
# reachable over the websocket transport but has gone quiet (e.g. unplugged) -
# confirmed against the developer docs and by observing a real device unplug
# live (no EVENT_APC_WIFI_REMOVED, no message of any kind, ever arrives). The
# official app faces the same gap and also falls back to a silence timeout.
# Observed push cadence is ~2s continuously whether idle or cooking, so this
# is a large safety margin (~150x) against false positives, and spans several
# of this coordinator's own RECONNECT_RETRY_DELAY poll cycles.
DEVICE_STALE_THRESHOLD = timedelta(minutes=5)


@dataclass
class AnovaData:
    """Data for the Anova integration."""

    api_jwt: str
    coordinators: list[AnovaCoordinator]
    api: AnovaApi
    reconnect_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    # Backs off reconnect attempts on repeated failure so a persistently
    # unreachable/unresponsive Anova cloud isn't hammered with a fresh
    # websocket + auth attempt every RECONNECT_RETRY_DELAY forever (observed
    # live: 825 failed attempts over 15h on a fixed interval). Reset to the
    # base delay as soon as a reconnect succeeds.
    reconnect_backoff: timedelta = timedelta(seconds=RECONNECT_RETRY_DELAY)
    next_reconnect_attempt: datetime | None = None


type AnovaConfigEntry = ConfigEntry[AnovaData]


class AnovaCoordinator(DataUpdateCoordinator[APCUpdate | None]):
    """Anova custom coordinator."""

    config_entry: AnovaConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: AnovaConfigEntry,
        anova_device: APCWifiDevice,
    ) -> None:
        """Set up Anova Coordinator."""
        super().__init__(
            hass,
            config_entry=config_entry,
            name="Anova Precision Cooker",
            logger=_LOGGER,
            update_interval=timedelta(seconds=RECONNECT_RETRY_DELAY),
        )
        self.device_unique_id = anova_device.cooker_id
        self.anova_device = anova_device
        self.device_info: DeviceInfo | None = None

        self.device_info = DeviceInfo(
            identifiers={(DOMAIN, self.device_unique_id)},
            name="Anova Precision Cooker",
            manufacturer="Anova",
            model="Precision Cooker",
        )
        self.sensor_data_set: bool = False
        # Owned by the coordinator, not the number entities, so it's seeded
        # from the device's own state (see _handle_device_update) regardless
        # of entity setup ordering.
        self.pending_target_temperature: float | None = None
        self.pending_cook_time_seconds: int | None = None
        self.anova_device.set_update_listener(self._handle_device_update)
        if (last_update := anova_device.last_update) is not None:
            self._handle_device_update(last_update)

    def _handle_device_update(self, update: APCUpdate) -> None:
        """Seed the pending target temperature/timer on first data, then propagate."""
        if self.pending_target_temperature is None:
            self.pending_target_temperature = update.sensor.target_temperature
        if self.pending_cook_time_seconds is None:
            self.pending_cook_time_seconds = update.sensor.cook_time
        self.async_set_updated_data(update)

    @callback
    def async_start_disconnect_listener(self) -> None:
        """Register a done callback on the websocket listener to detect connection drops."""
        ws_handler = self.config_entry.runtime_data.api.websocket_handler
        if ws_handler is None or ws_handler._message_listener is None:  # noqa: SLF001
            return

        @callback
        def _on_done(task: asyncio.Future[None]) -> None:
            if task.cancelled():
                return
            if self.config_entry.state is not ConfigEntryState.LOADED:
                return
            self.config_entry.async_create_background_task(
                self.hass,
                self.async_request_refresh(),
                "anova_websocket_reconnect",
            )

        ws_handler._message_listener.add_done_callback(_on_done)  # noqa: SLF001

    def _data_if_fresh(self) -> APCUpdate | None:
        """Return the last push, or None if the device has gone quiet.

        "Quiet" means no push for longer than DEVICE_STALE_THRESHOLD.
        """
        last_seen = self.anova_device.last_update_received_at
        if last_seen is None or dt_util.utcnow() - last_seen > DEVICE_STALE_THRESHOLD:
            return None
        return self.data

    @override
    async def _async_update_data(self) -> APCUpdate | None:
        """Reconnect the websocket if it has dropped; return current push data."""
        ws_handler = self.config_entry.runtime_data.api.websocket_handler
        if ws_handler is not None:
            listener = ws_handler._message_listener  # noqa: SLF001
            if listener is not None and not listener.done():
                return self._data_if_fresh()

        async with self.config_entry.runtime_data.reconnect_lock:
            ws_handler = self.config_entry.runtime_data.api.websocket_handler
            if ws_handler is not None:
                listener = ws_handler._message_listener  # noqa: SLF001
                if listener is not None and not listener.done():
                    return self._data_if_fresh()
            next_attempt = self.config_entry.runtime_data.next_reconnect_attempt
            if next_attempt is None or dt_util.utcnow() >= next_attempt:
                await self._async_reconnect()

        return self._data_if_fresh()

    def _schedule_reconnect_backoff(self) -> None:
        """Push the next reconnect attempt out and grow the backoff for next time."""
        data = self.config_entry.runtime_data
        data.next_reconnect_attempt = dt_util.utcnow() + data.reconnect_backoff
        data.reconnect_backoff = min(data.reconnect_backoff * 2, MAX_RECONNECT_BACKOFF)

    async def _async_reconnect(self) -> None:
        """Reconnect the Anova websocket and re-wire all device coordinators."""
        api = self.config_entry.runtime_data.api
        _LOGGER.warning("Anova websocket connection lost, attempting to reconnect")
        try:
            await api.create_websocket()
        except NoDevicesFound, WebsocketFailure:
            # A stale JWT can connect fine but never have the device attached to
            # it (NoDevicesFound) as easily as it can fail outright
            # (WebsocketFailure) - re-authenticate on either so we don't keep
            # retrying with the same session that's already stopped working.
            try:
                await api.authenticate()
            except InvalidLogin as err:
                _LOGGER.error("Anova re-authentication failed: %s", err)
                self._schedule_reconnect_backoff()
                raise UpdateFailed(str(err)) from err
            except LoginUnreachable as err:
                _LOGGER.warning("Failed to re-authenticate with Anova: %s", err)
                self._schedule_reconnect_backoff()
                raise UpdateFailed(str(err)) from err
            try:
                await api.create_websocket()
            except (NoDevicesFound, WebsocketFailure) as err:
                _LOGGER.warning("Failed to reconnect to Anova websocket: %s", err)
                self._schedule_reconnect_backoff()
                raise UpdateFailed(str(err)) from err

        data = self.config_entry.runtime_data
        data.reconnect_backoff = timedelta(seconds=RECONNECT_RETRY_DELAY)
        data.next_reconnect_attempt = None

        ws_handler = api.websocket_handler
        if ws_handler is None:
            return

        for coordinator in self.config_entry.runtime_data.coordinators:
            device = ws_handler.devices.get(coordinator.device_unique_id)
            if device is not None:
                coordinator.anova_device = device
                device.set_update_listener(coordinator._handle_device_update)  # noqa: SLF001
                if (last_update := device.last_update) is not None:
                    coordinator._handle_device_update(last_update)  # noqa: SLF001

        self.async_start_disconnect_listener()
