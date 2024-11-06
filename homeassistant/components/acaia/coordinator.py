"""Coordinator for Acaia integration."""

from __future__ import annotations

from datetime import timedelta
import logging

from pyacaia_async.acaiascale import AcaiaScale
from pyacaia_async.exceptions import AcaiaDeviceNotFound, AcaiaError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MAC
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_IS_NEW_STYLE_SCALE

SCAN_INTERVAL = timedelta(seconds=15)

_LOGGER = logging.getLogger(__name__)

type AcaiaConfigEntry = ConfigEntry[AcaiaCoordinator]


class AcaiaCoordinator(DataUpdateCoordinator[None]):
    """Class to handle fetching data from the La Marzocco API centrally."""

    config_entry: AcaiaConfigEntry

    @property
    def scale(self) -> AcaiaScale:
        """Return the scale object."""
        return self._scale

    def __init__(self, hass: HomeAssistant, entry: AcaiaConfigEntry) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Acaia coordinator",
            update_interval=SCAN_INTERVAL,
            config_entry=entry,
        )

        self._scale = AcaiaScale(
            mac=entry.data[CONF_MAC],
            is_new_style_scale=entry.data[CONF_IS_NEW_STYLE_SCALE],
            notify_callback=self.async_update_listeners,
        )

    async def _async_update_data(self) -> None:
        """Fetch data."""

        # scale is already connected, return
        if self._scale.connected:
            return

        # scale is not connected, try to connect
        try:
            await self._scale.connect(setup_tasks=False)
        except (AcaiaDeviceNotFound, AcaiaError, TimeoutError) as ex:
            _LOGGER.debug(
                "Could not connect to scale: %s, Error: %s", self._scale.mac, ex
            )
            self._scale.connected = False
            self._scale.timer_running = False
            self._scale.async_empty_queue_and_cancel_tasks()
            self.async_update_listeners()
            raise UpdateFailed from ex

        # connected, set up background tasks
        if not self.scale.heartbeat_task or self.scale.heartbeat_task.done():
            self.scale.heartbeat_task = self.config_entry.async_create_background_task(
                hass=self.hass,
                target=self.scale.send_heartbeats(),
                name="acaia_heartbeat_task",
            )

        if not self.scale.process_queue_task or self.scale.process_queue_task.done():
            self.scale.process_queue_task = (
                self.config_entry.async_create_background_task(
                    hass=self.hass,
                    target=self.scale.process_queue(),
                    name="acaia_process_queue_task",
                )
            )
