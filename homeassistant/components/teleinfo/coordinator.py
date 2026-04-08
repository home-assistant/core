"""DataUpdateCoordinator for the Teleinfo integration."""

from __future__ import annotations

from datetime import timedelta
import logging

import serial
from teleinfo import decode, read_frame

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_SERIAL_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=10)

type TeleinfoConfigEntry = ConfigEntry[TeleinfoCoordinator]


class TeleinfoCoordinator(DataUpdateCoordinator[dict[str, str]]):
    """Teleinfo data update coordinator."""

    config_entry: TeleinfoConfigEntry

    def __init__(self, hass: HomeAssistant, entry: TeleinfoConfigEntry) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )

    async def _async_update_data(self) -> dict[str, str]:
        """Read a Teleinfo frame from the serial port and decode it."""
        port = self.config_entry.data[CONF_SERIAL_PORT]

        try:
            frame = await self.hass.async_add_executor_job(read_frame, port)
        except serial.SerialException as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="communication_error",
            ) from err
        except TimeoutError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="timeout_error",
            ) from err

        try:
            return decode(frame)
        except Exception as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="decode_error",
            ) from err
