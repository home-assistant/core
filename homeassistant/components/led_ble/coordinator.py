"""The LED BLE coordinator."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging

from led_ble import BLEAK_EXCEPTIONS, LEDBLE

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import UPDATE_SECONDS

type LEDBLEConfigEntry = ConfigEntry[LEDBLEData]


@dataclass
class LEDBLEData:
    """Data for the led ble integration."""

    title: str
    device: LEDBLE
    coordinator: LEDBLECoordinator


_LOGGER = logging.getLogger(__name__)


class LEDBLECoordinator(DataUpdateCoordinator[None]):
    """Class to manage fetching LED BLE data."""

    config_entry: LEDBLEConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: LEDBLEConfigEntry,
        led_ble: LEDBLE,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=led_ble.name,
            update_interval=timedelta(seconds=UPDATE_SECONDS),
        )
        self.led_ble = led_ble

    async def _async_update_data(self) -> None:
        """Update the device state."""
        try:
            await self.led_ble.update()
        except BLEAK_EXCEPTIONS as ex:
            raise UpdateFailed(str(ex)) from ex
