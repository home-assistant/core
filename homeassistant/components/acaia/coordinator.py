"""Coordinator for Acaia integration."""

from __future__ import annotations

from datetime import timedelta
import logging

from aioacaia.acaiascale import AcaiaScale
from aioacaia.exceptions import AcaiaDeviceNotFound, AcaiaError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONF_IS_NEW_STYLE_SCALE

SCAN_INTERVAL = timedelta(seconds=15)

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

        self._scale = AcaiaScale(
            address_or_ble_device=entry.data[CONF_ADDRESS],
            name=entry.title,
            is_new_style_scale=entry.data[CONF_IS_NEW_STYLE_SCALE],
            notify_callback=self.async_update_listeners,
        )

    @property
    def scale(self) -> AcaiaScale:
        """Return the scale object."""
        return self._scale

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
                "Could not connect to scale: %s, Error: %s",
                self.config_entry.data[CONF_ADDRESS],
                ex,
            )
            self._scale.device_disconnected_handler(notify=False)
            return

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
