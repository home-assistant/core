"""The coordinator for APsystems local API integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from aiohttp import ClientConnectionError
from APsystemsEZ1 import (
    APsystemsEZ1M,
    InverterReturnedError,
    ReturnAlarmInfo,
    ReturnOutputData,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER


@dataclass
class ApSystemsSensorData:
    """Representing different Apsystems sensor data."""

    output_data: ReturnOutputData
    alarm_info: ReturnAlarmInfo


@dataclass
class ApSystemsData:
    """Store runtime data."""

    coordinator: ApSystemsDataCoordinator
    device_id: str


type ApSystemsConfigEntry = ConfigEntry[ApSystemsData]


class ApSystemsDataCoordinator(DataUpdateCoordinator[ApSystemsSensorData]):
    """Coordinator used for all sensors."""

    config_entry: ApSystemsConfigEntry
    device_version: str
    battery_system: bool

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ApSystemsConfigEntry,
        api: APsystemsEZ1M,
    ) -> None:
        """Initialize my coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name="APSystems Data",
            update_interval=timedelta(seconds=12),
        )
        self.api = api
        self.api.max_power = getattr(self.api, "max_power", 800)
        self.api.min_power = getattr(self.api, "min_power", 30)
        self.device_version = ""
        self.battery_system = False
        self.inverter_connected = False

    async def _async_setup(self) -> None:
        try:
            await self._fetch_device_info()
        except ConnectionError, TimeoutError, ClientConnectionError:
            # Inverter may be offline (e.g. nighttime). Allow setup to
            # continue so entities are created; device info will be
            # fetched on the first successful update instead.
            self.inverter_connected = False
            LOGGER.debug("Inverter not reachable during setup, continuing anyway")

    async def _fetch_device_info(self) -> None:
        """Fetch device info from inverter and store on coordinator."""
        device_info = await self.api.get_device_info()
        self.api.max_power = device_info.maxPower
        self.api.min_power = device_info.minPower
        self.device_version = device_info.devVer
        self.battery_system = device_info.isBatterySystem

        # Update device registry if the device was already registered
        # (happens when device info was unavailable during initial setup)
        registry = dr.async_get(self.hass)
        assert self.config_entry.unique_id
        device_entry = registry.async_get_device(
            identifiers={(DOMAIN, self.config_entry.unique_id)}
        )
        if device_entry:
            version_parts = device_info.devVer.split(" ")
            sw_version = (
                version_parts[1] if len(version_parts) > 1 else version_parts[0]
            )
            registry.async_update_device(device_entry.id, sw_version=sw_version)

    async def _async_update_data(self) -> ApSystemsSensorData:
        try:
            # Fetch device info if it wasn't available during setup
            if not self.device_version:
                await self._fetch_device_info()
            output_data = await self.api.get_output_data()
            alarm_info = await self.api.get_alarm_info()
        except InverterReturnedError:
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key="inverter_error"
            ) from None
        except ConnectionError, TimeoutError, ClientConnectionError:
            # The inverter shuts down at night when there is no solar power,
            # causing connection errors. Return power as 0 since the inverter
            # is not producing. Energy values use last known data if available,
            # or None to avoid a false spike in TOTAL_INCREASING statistics
            # when the inverter comes back online with real values.
            self.inverter_connected = False
            last = self.data
            if last:
                LOGGER.debug(
                    "Inverter offline, using last known energy values with zero power"
                )
                return ApSystemsSensorData(
                    output_data=ReturnOutputData(
                        p1=0,
                        p2=0,
                        e1=last.output_data.e1,
                        e2=last.output_data.e2,
                        te1=last.output_data.te1,
                        te2=last.output_data.te2,
                    ),
                    alarm_info=last.alarm_info,
                )
            LOGGER.debug(
                "Inverter offline, no previous data available, reporting zero power"
            )
            return ApSystemsSensorData(
                output_data=ReturnOutputData(
                    p1=0, p2=0, e1=None, e2=None, te1=None, te2=None
                ),
                alarm_info=ReturnAlarmInfo(
                    offgrid=False,
                    shortcircuit_1=False,
                    shortcircuit_2=False,
                    operating=True,
                ),
            )
        self.inverter_connected = True
        return ApSystemsSensorData(output_data=output_data, alarm_info=alarm_info)
