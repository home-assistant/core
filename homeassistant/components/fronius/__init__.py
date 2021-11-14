"""The Fronius integration."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import Callable, TypeVar

from pyfronius import Fronius

from homeassistant.core import HomeAssistant

from .const import (
    DEFAULT_UPDATE_INTERVAL,
    DEFAULT_UPDATE_INTERVAL_LOGGER,
    DEFAULT_UPDATE_INTERVAL_POWER_FLOW,
    DOMAIN,
    SOLAR_NET_ID_SYSTEM,
    FroniusDeviceInfo,
)
from .coordinator import (
    FroniusCoordinatorBase,
    FroniusInverterUpdateCoordinator,
    FroniusLoggerUpdateCoordinator,
    FroniusMeterUpdateCoordinator,
    FroniusPowerFlowUpdateCoordinator,
    FroniusStorageUpdateCoordinator,
)

_LOGGER = logging.getLogger(__name__)

FroniusCoordinatorType = TypeVar("FroniusCoordinatorType", bound=FroniusCoordinatorBase)


class FroniusSolarNet:
    """The FroniusSolarNet class routes received values to sensor entities."""

    def __init__(self, hass: HomeAssistant, fronius: Fronius, host: str) -> None:
        """Initialize FroniusSolarNet class."""
        self.hass = hass
        self.cleanup_callbacks: list[Callable[[], None]] = []
        self.coordinator_lock = asyncio.Lock()
        self.host = host
        # solar_net_device_id is either logger uid or first inverter uid if no logger available
        # prepended by "solar_net_" to have individual device for whole system (power_flow)
        self.solar_net_device_id: str = ""

        self.fronius = fronius
        self.inverter_coordinators: list[FroniusInverterUpdateCoordinator] = []
        self.logger_coordinator: FroniusLoggerUpdateCoordinator | None = None
        self.meter_coordinator: FroniusMeterUpdateCoordinator | None = None
        self.power_flow_coordinator: FroniusPowerFlowUpdateCoordinator | None = None
        self.storage_coordinator: FroniusStorageUpdateCoordinator | None = None

    async def init_devices(self) -> None:
        """Initialize DataUpdateCoordinators for SolarNet devices."""
        # Gen24 devices don't provide GetLoggerInfo
        self.logger_coordinator = await self._init_optional_coordinator(
            FroniusLoggerUpdateCoordinator(
                hass=self.hass,
                solar_net=self,
                logger=_LOGGER,
                name=f"{DOMAIN}_logger_{self.host}",
                update_interval=timedelta(seconds=DEFAULT_UPDATE_INTERVAL_LOGGER),
            )
        )
        if self.logger_coordinator:
            logger_uid = self.logger_coordinator.data[SOLAR_NET_ID_SYSTEM][
                "unique_identifier"
            ]["value"]
            self.solar_net_device_id = f"solar_net_{logger_uid}"

        _inverter_infos = await self._get_inverter_infos()
        for inverter_info in _inverter_infos:
            coordinator = FroniusInverterUpdateCoordinator(
                hass=self.hass,
                solar_net=self,
                logger=_LOGGER,
                name=f"{DOMAIN}_inverter_{inverter_info.solar_net_id}_{self.host}",
                update_interval=timedelta(seconds=DEFAULT_UPDATE_INTERVAL),
                inverter_info=inverter_info,
            )
            await coordinator.async_refresh()
            self.inverter_coordinators.append(coordinator)

        self.meter_coordinator = await self._init_optional_coordinator(
            FroniusMeterUpdateCoordinator(
                hass=self.hass,
                solar_net=self,
                logger=_LOGGER,
                name=f"{DOMAIN}_meters_{self.host}",
                update_interval=timedelta(seconds=DEFAULT_UPDATE_INTERVAL),
            )
        )

        self.power_flow_coordinator = await self._init_optional_coordinator(
            FroniusPowerFlowUpdateCoordinator(
                hass=self.hass,
                solar_net=self,
                logger=_LOGGER,
                name=f"{DOMAIN}_power_flow_{self.host}",
                update_interval=timedelta(seconds=DEFAULT_UPDATE_INTERVAL_POWER_FLOW),
            )
        )

        self.storage_coordinator = await self._init_optional_coordinator(
            FroniusStorageUpdateCoordinator(
                hass=self.hass,
                solar_net=self,
                logger=_LOGGER,
                name=f"{DOMAIN}_storages_{self.host}",
                update_interval=timedelta(seconds=DEFAULT_UPDATE_INTERVAL),
            )
        )

    async def _get_inverter_infos(self) -> list[FroniusDeviceInfo]:
        """Get information about the inverters in the SolarNet system."""
        _inverter_info = await self.fronius.inverter_info()

        inverter_infos: list[FroniusDeviceInfo] = []
        for inverter in _inverter_info["inverters"]:
            solar_net_id = inverter["device_id"]["value"]
            unique_id = inverter["unique_id"]["value"]
            inverter_infos.append(
                FroniusDeviceInfo(
                    solar_net_id=solar_net_id,
                    unique_id=unique_id,
                )
            )
        if not self.solar_net_device_id:
            first_inverter_uid: str = inverter_infos[0].unique_id
            self.solar_net_device_id = f"solar_net_{first_inverter_uid}"

        return inverter_infos

    @staticmethod
    async def _init_optional_coordinator(
        coordinator: FroniusCoordinatorType,
    ) -> FroniusCoordinatorType | None:
        """Initialize an update coordinator and return it if devices are found."""
        await coordinator.async_refresh()
        if coordinator.last_update_success is False:
            return None
        # keep coordinator only if devices are found
        # else ConfigEntryNotReady raised form KeyError
        # in FroniusMeterUpdateCoordinator._get_fronius_device_data
        return coordinator
