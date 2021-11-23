"""The Fronius integration."""
from __future__ import annotations

import asyncio
import logging
from typing import Callable, TypeVar

from pyfronius import Fronius, FroniusError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_MODEL, ATTR_SW_VERSION, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN, SOLAR_NET_ID_SYSTEM, FroniusDeviceInfo
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
        self.system_device_info: DeviceInfo | None = None

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
            )
            await self.logger_coordinator.async_config_entry_first_refresh()

        # _create_solar_net_device uses data from self.logger_coordinator when available
        self.system_device_info = await self._create_solar_net_device()

        _inverter_infos = await self._get_inverter_infos()
        for inverter_info in _inverter_infos:
            coordinator = FroniusInverterUpdateCoordinator(
                hass=self.hass,
                solar_net=self,
                logger=_LOGGER,
                name=f"{DOMAIN}_inverter_{inverter_info.solar_net_id}_{self.host}",
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
            )
        )

        self.power_flow_coordinator = await self._init_optional_coordinator(
            FroniusPowerFlowUpdateCoordinator(
                hass=self.hass,
                solar_net=self,
                logger=_LOGGER,
                name=f"{DOMAIN}_power_flow_{self.host}",
            )
        )

        self.storage_coordinator = await self._init_optional_coordinator(
            FroniusStorageUpdateCoordinator(
                hass=self.hass,
                solar_net=self,
                logger=_LOGGER,
                name=f"{DOMAIN}_storages_{self.host}",
            )
        )

    async def _create_solar_net_device(self) -> DeviceInfo:
        """Create a device for the Fronius SolarNet system."""
        solar_net_device: DeviceInfo = DeviceInfo(
            configuration_url=self.host,
            identifiers={(DOMAIN, self.solar_net_device_id)},
            manufacturer="Fronius",
            name="SolarNet",
        )
        if self.logger_coordinator:
            _logger_info = self.logger_coordinator.data[SOLAR_NET_ID_SYSTEM]
            solar_net_device[ATTR_MODEL] = _logger_info["product_type"]["value"]
            solar_net_device[ATTR_SW_VERSION] = _logger_info["software_version"][
                "value"
            ]

        device_registry = await dr.async_get_registry(self.hass)
        device_registry.async_get_or_create(
            config_entry_id=self.config_entry.entry_id,
            **solar_net_device,
        )
        return solar_net_device

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
            device_info = DeviceInfo(
                identifiers={(DOMAIN, unique_id)},
                manufacturer=inverter["device_type"].get("manufacturer", "Fronius"),
                model=inverter["device_type"].get(
                    "model", inverter["device_type"]["value"]
                ),
                name=inverter.get("custom_name", {}).get("value"),
                via_device=(DOMAIN, self.solar_net_device_id),
            )
            inverter_infos.append(
                FroniusDeviceInfo(
                    device_info=device_info,
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
