"""The coordinator for APsystems local API integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from APsystemsEZ1 import (
    APsystemsEZ1M,
    InverterReturnedError,
    ReturnAlarmInfo,
    ReturnOutputData,
)

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER


@dataclass
class ApSystemsSensorData:
    """Representing different Apsystems sensor data."""

    output_data: ReturnOutputData
    alarm_info: ReturnAlarmInfo


class ApSystemsDataCoordinator(DataUpdateCoordinator[ApSystemsSensorData]):
    """Coordinator used for all sensors."""

    device_version: str

    def __init__(self, hass: HomeAssistant, api: APsystemsEZ1M) -> None:
        """Initialize my coordinator."""
        super().__init__(
            hass,
            LOGGER,
            name="APSystems Data",
            update_interval=timedelta(seconds=12),
        )
        self.api = api

    async def _async_setup(self) -> None:
        try:
            device_info = await self.api.get_device_info()
        except (ConnectionError, TimeoutError):
            raise UpdateFailed from None
        self.api.max_power = device_info.maxPower
        self.api.min_power = device_info.minPower
        self.device_version = device_info.devVer

    async def _async_update_data(self) -> ApSystemsSensorData:
        try:
            output_data = await self.api.get_output_data()
            alarm_info = await self.api.get_alarm_info()
        except InverterReturnedError:
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key="inverter_error"
            ) from None
        return ApSystemsSensorData(output_data=output_data, alarm_info=alarm_info)
