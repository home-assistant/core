"""Coordinator for Acaia integration."""

from datetime import timedelta
import logging
from typing import override

from aioacaia import AcaiaScale
from aioacaia.exceptions import AcaiaDeviceNotFound, AcaiaError

from homeassistant.components.bluetooth import (
    MONOTONIC_TIME,
    BluetoothServiceInfoBleak,
    async_get_scanner,
    async_register_advertisement_callback,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import CONF_IDLE_TIMEOUT, CONF_IS_NEW_STYLE_SCALE, DEFAULT_IDLE_TIMEOUT

SCAN_INTERVAL = timedelta(seconds=15)
# Silence that means the scale turned off. Bluetooth's own unavailable tracking takes
# up to 8 minutes to notice, so a scale turned back on before that would be missed.
SCALE_OFF_AFTER_SILENCE = 30
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

        # Minutes without a weight change before disconnecting, 0 disables.
        self._idle_timeout: int = entry.options.get(
            CONF_IDLE_TIMEOUT, DEFAULT_IDLE_TIMEOUT
        )
        self._last_weight: float | None = None
        self._last_activity = dt_util.utcnow()
        self._idle_disconnected = False
        self._last_seen = 0.0

    @property
    def scale(self) -> AcaiaScale:
        """Return the scale object."""
        return self._scale

    @override
    async def _async_setup(self) -> None:
        """Watch advertisements to notice the scale turning off and on again."""
        self.config_entry.async_on_unload(
            async_register_advertisement_callback(
                self.hass,
                self._async_handle_advertisement,
                self.config_entry.data[CONF_ADDRESS],
            )
        )

    async def async_stop(self) -> None:
        """Disconnect from the scale."""
        if self._scale.connected:
            await self._scale.disconnect()

    @callback
    def _async_handle_notification(self) -> None:
        """Track weight changes before notifying entities."""
        if self._scale.weight != self._last_weight:
            self._last_weight = self._scale.weight
            self._last_activity = dt_util.utcnow()
        self._debouncer.async_schedule_call()

    @callback
    def _async_handle_advertisement(
        self, service_info: BluetoothServiceInfoBleak
    ) -> None:
        """Allow reconnecting once the scale has turned off and on again.

        The scale keeps advertising after an idle disconnect until its own auto-off
        timer fires, so reconnecting while it advertises would keep it awake forever.
        It does not advertise while connected, so silence only counts from the
        disconnect onwards.
        """
        if (
            self._idle_disconnected
            and service_info.time - self._last_seen > SCALE_OFF_AFTER_SILENCE
        ):
            self._idle_disconnected = False
        self._last_seen = service_info.time

    @override
    async def _async_update_data(self) -> None:
        """Fetch data."""

        if (
            self._scale.connected
            and self._idle_timeout
            and dt_util.utcnow() - self._last_activity
            >= timedelta(minutes=self._idle_timeout)
        ):
            _LOGGER.debug(
                "No weight change on scale %s for %s minutes, disconnecting",
                self.config_entry.data[CONF_ADDRESS],
                self._idle_timeout,
            )
            self._idle_disconnected = True
            self._last_seen = MONOTONIC_TIME()
            await self._scale.disconnect()

        # waiting for the scale to turn off and on again, return
        if self._idle_disconnected:
            return

        # scale is already connected, return
        if self._scale.connected:
            return

        # scale is not connected, try to connect
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
