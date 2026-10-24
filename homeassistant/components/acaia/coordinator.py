"""Coordinator for Acaia integration."""

from datetime import timedelta
import logging
from typing import override

from aioacaia import AcaiaScale
from aioacaia.exceptions import AcaiaDeviceNotFound, AcaiaError

from homeassistant.components.bluetooth import (
    BluetoothCallbackMatcher,
    BluetoothCallbackReplay,
    BluetoothChange,
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
    async_get_scanner,
    async_register_callback,
    async_track_unavailable,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import CONF_IDLE_TIMEOUT, CONF_IS_NEW_STYLE_SCALE, CONF_KEEP_CONNECTED

SCAN_INTERVAL = timedelta(seconds=15)
UPDATE_DEBOUNCE_TIME = 0.2

_LOGGER = logging.getLogger(__name__)

type AcaiaConfigEntry = ConfigEntry[AcaiaCoordinator]


class AcaiaCoordinator(DataUpdateCoordinator[None]):
    """Class to handle fetching data from the scale."""

    config_entry: AcaiaConfigEntry

    def __init__(self, hass: HomeAssistant, entry: AcaiaConfigEntry) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="acaia coordinator",
            update_interval=SCAN_INTERVAL,
            config_entry=entry,
        )

        self._debouncer = Debouncer(
            hass=hass,
            logger=_LOGGER,
            cooldown=UPDATE_DEBOUNCE_TIME,
            immediate=True,
            function=self.async_update_listeners,
        )

        self._scale = AcaiaScale(
            address_or_ble_device=entry.data[CONF_ADDRESS],
            name=entry.title,
            is_new_style_scale=entry.data[CONF_IS_NEW_STYLE_SCALE],
            notify_callback=self._async_handle_notification,
            scanner=async_get_scanner(hass),
        )

        # Read from options so the preference applies before the first refresh.
        self.keep_connected: bool = entry.options.get(CONF_KEEP_CONNECTED, True)

        # Minutes without a weight change before disconnecting, 0 disables.
        self.idle_timeout: int = entry.options.get(CONF_IDLE_TIMEOUT, 0)
        self._last_weight: float | None = None
        self._last_activity = dt_util.utcnow()
        self._idle_disconnected = False
        self._asleep_after_idle = False

        # The scale keeps advertising after an idle disconnect until its own
        # auto-off timer fires, so reconnecting on any advertisement would wake
        # it right back up. Only reconnect once it has gone silent and returns.
        address = entry.data[CONF_ADDRESS]
        entry.async_on_unload(
            async_track_unavailable(hass, self._async_handle_unavailable, address)
        )
        entry.async_on_unload(
            async_register_callback(
                hass,
                self._async_handle_advertisement,
                BluetoothCallbackMatcher(address=address, connectable=True),
                BluetoothScanningMode.PASSIVE,
                replay=BluetoothCallbackReplay.DISABLED,
            )
        )

    @property
    def scale(self) -> AcaiaScale:
        """Return the scale object."""
        return self._scale

    async def async_set_keep_connected(self, keep_connected: bool) -> None:
        """Enable or disable keeping a persistent connection to the scale."""
        self.keep_connected = keep_connected
        self.hass.config_entries.async_update_entry(
            self.config_entry,
            options={**self.config_entry.options, CONF_KEEP_CONNECTED: keep_connected},
        )
        if keep_connected:
            self._clear_idle_disconnect()
            await self._async_ensure_connected()
        elif self._scale.connected:
            await self._scale.disconnect()

    async def async_set_idle_timeout(self, idle_timeout: int) -> None:
        """Set the minutes without a weight change before disconnecting."""
        self.idle_timeout = idle_timeout
        self.hass.config_entries.async_update_entry(
            self.config_entry,
            options={**self.config_entry.options, CONF_IDLE_TIMEOUT: idle_timeout},
        )
        if not idle_timeout and self._idle_disconnected:
            self._clear_idle_disconnect()
            await self.async_request_refresh()

    @callback
    def _async_handle_notification(self) -> None:
        """Track weight changes before notifying entities."""
        if self._scale.weight != self._last_weight:
            self._last_weight = self._scale.weight
            self._last_activity = dt_util.utcnow()
        self._debouncer.async_schedule_call()

    @callback
    def _async_handle_unavailable(
        self, service_info: BluetoothServiceInfoBleak
    ) -> None:
        """Note that the scale went to sleep after an idle disconnect."""
        if self._idle_disconnected:
            self._asleep_after_idle = True

    @callback
    def _async_handle_advertisement(
        self, service_info: BluetoothServiceInfoBleak, change: BluetoothChange
    ) -> None:
        """Reconnect once the scale is turned back on after sleeping."""
        if not self._asleep_after_idle:
            return
        self._clear_idle_disconnect()
        self.config_entry.async_create_task(self.hass, self.async_request_refresh())

    def _clear_idle_disconnect(self) -> None:
        """Allow the coordinator to reconnect to the scale again."""
        self._idle_disconnected = False
        self._asleep_after_idle = False

    @override
    async def _async_update_data(self) -> None:
        """Fetch data."""

        if not self.keep_connected or self._idle_disconnected:
            return

        if not self._scale.connected:
            await self._async_ensure_connected()
            return

        if self.idle_timeout and dt_util.utcnow() - self._last_activity >= timedelta(
            minutes=self.idle_timeout
        ):
            _LOGGER.debug(
                "No weight change on scale %s for %s minutes, disconnecting",
                self.config_entry.data[CONF_ADDRESS],
                self.idle_timeout,
            )
            self._idle_disconnected = True
            await self._scale.disconnect()

    async def _async_ensure_connected(self) -> None:
        """Connect to the scale and set up its background tasks if needed."""

        if self._scale.connected:
            return

        try:
            await self._scale.connect(setup_tasks=False)
        except (AcaiaDeviceNotFound, AcaiaError, TimeoutError) as ex:
            _LOGGER.debug(
                "Could not connect to scale: %s, Error: %s",
                self.config_entry.data[CONF_ADDRESS],
                ex,
            )
            self._scale.device_disconnected_handler(notify=False)
            return

        # keep_connected may have been turned off while connect() was pending.
        if not self.keep_connected:
            await self._scale.disconnect()
            return

        self._last_activity = dt_util.utcnow()

        # connected, set up background tasks
        if not self._scale.heartbeat_task or self._scale.heartbeat_task.done():
            self._scale.heartbeat_task = self.config_entry.async_create_background_task(
                hass=self.hass,
                target=self._scale.send_heartbeats(),
                name="acaia_heartbeat_task",
            )

        if not self._scale.process_queue_task or self._scale.process_queue_task.done():
            self._scale.process_queue_task = (
                self.config_entry.async_create_background_task(
                    hass=self.hass,
                    target=self._scale.process_queue(),
                    name="acaia_process_queue_task",
                )
            )
