"""Polling state for BUSY Bar."""

from datetime import timedelta
import logging
from typing import override

from busylib import AsyncBusyBar
from busylib.exceptions import BusyBarError
from busylib.types import WifiState
from pydantic import BaseModel

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)
type BusyConfigEntry = ConfigEntry[BusyCoordinator]


class BusyData(BaseModel):
    """Readings and device metadata from one poll."""

    battery: int | None
    wifi_signal: int | None
    wifi_ssid: str | None
    serial: str | None
    hardware: str | None
    firmware: str | None


class BusyCoordinator(DataUpdateCoordinator[BusyData]):
    """Read two endpoints every thirty seconds."""

    def __init__(
        self, hass: HomeAssistant, entry: BusyConfigEntry, client: AsyncBusyBar
    ) -> None:
        """Initialize the shared polling client.

        Bind the shared coordinator and the state required by this instance.
        """
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=entry.title,
            update_interval=timedelta(seconds=30),
            always_update=False,
        )
        self.client = client

    @override
    async def _async_update_data(self) -> BusyData:
        """Map device responses into the integration's polling state.

        Translate the status and Wi-Fi responses without collecting a full snapshot.
        """
        try:
            status = await self.client.status()
            wifi = await self.client.wifi_status()
        except BusyBarError as err:
            raise UpdateFailed("Cannot read BUSY Bar") from err
        firmware = status.firmware
        return BusyData(
            battery=status.power.battery_charge if status.power else None,
            wifi_signal=wifi.rssi if wifi.state == WifiState.CONNECTED else None,
            wifi_ssid=wifi.ssid if wifi.state == WifiState.CONNECTED else None,
            serial=status.device.serial_number if status.device else None,
            hardware=status.device.otp_model if status.device else None,
            firmware=(
                f"{firmware.version}"
                + (f" ({firmware.branch})" if firmware.branch else "")
                if firmware and firmware.version
                else None
            ),
        )
