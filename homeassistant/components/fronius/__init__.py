"""The Fronius integration."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import Callable, TypeVar

from pyfronius import Fronius, FroniusError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    DEFAULT_UPDATE_INTERVAL,
    DEFAULT_UPDATE_INTERVAL_LOGGER,
    DEFAULT_UPDATE_INTERVAL_POWER_FLOW,
    DOMAIN,
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
PLATFORMS: list[str] = ["sensor"]

FroniusCoordinatorType = TypeVar("FroniusCoordinatorType", bound=FroniusCoordinatorBase)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up fronius from a config entry."""
    host = entry.data[CONF_HOST]
    fronius = Fronius(async_get_clientsession(hass), host)
    solar_net = FroniusSolarNet(hass, entry, fronius)
    await solar_net.init_devices()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = solar_net
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    # reload on config_entry update
    entry.async_on_unload(entry.add_update_listener(async_update_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        solar_net = hass.data[DOMAIN].pop(entry.entry_id)
        while solar_net.cleanup_callbacks:
            solar_net.cleanup_callbacks.pop()()

    return unload_ok


async def async_update_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update a given config entry."""
    await hass.config_entries.async_reload(entry.entry_id)


class FroniusSolarNet:
    """The FroniusSolarNet class routes received values to sensor entities."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, fronius: Fronius
    ) -> None:
        """Initialize FroniusSolarNet class."""
        self.hass = hass
        self.cleanup_callbacks: list[Callable[[], None]] = []
        self.config_entry = entry
        self.coordinator_lock = asyncio.Lock()
        self.fronius = fronius
        self.host: str = entry.data[CONF_HOST]
        # entry.unique_id is either logger uid or first inverter uid if no logger available
        # prepended by "solar_net_" to have individual device for whole system (power_flow)
        self.solar_net_device_id = f"solar_net_{entry.unique_id}"

        self.inverter_coordinators: list[FroniusInverterUpdateCoordinator] = []
        self.logger_coordinator: FroniusLoggerUpdateCoordinator | None = None
        self.meter_coordinator: FroniusMeterUpdateCoordinator | None = None
        self.power_flow_coordinator: FroniusPowerFlowUpdateCoordinator | None = None
        self.storage_coordinator: FroniusStorageUpdateCoordinator | None = None

    async def init_devices(self) -> None:
        """Initialize DataUpdateCoordinators for SolarNet devices."""
        if self.config_entry.data["is_logger"]:
            self.logger_coordinator = FroniusLoggerUpdateCoordinator(
                hass=self.hass,
                solar_net=self,
                logger=_LOGGER,
                name=f"{DOMAIN}_logger_{self.host}",
                update_interval=timedelta(seconds=DEFAULT_UPDATE_INTERVAL_LOGGER),
            )
            await self.logger_coordinator.async_config_entry_first_refresh()

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
            await coordinator.async_config_entry_first_refresh()
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
        try:
            _inverter_info = await self.fronius.inverter_info()
        except FroniusError as err:
            raise ConfigEntryNotReady from err

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
        return inverter_infos

    @staticmethod
    async def _init_optional_coordinator(
        coordinator: FroniusCoordinatorType,
    ) -> FroniusCoordinatorType | None:
        """Initialize an update coordinator and return it if devices are found."""
        try:
            await coordinator.async_config_entry_first_refresh()
        except ConfigEntryNotReady:
            return None
        # keep coordinator only if devices are found
        # else ConfigEntryNotReady raised form KeyError
        # in FroniusMeterUpdateCoordinator._get_fronius_device_data
        return coordinator
