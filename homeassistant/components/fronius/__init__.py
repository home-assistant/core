"""The Fronius integration."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime, timedelta
import logging
from typing import Final, TypeVar

from pyfronius import Fronius, FroniusError

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import ATTR_MODEL, ATTR_SW_VERSION, CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    DOMAIN,
    SOLAR_NET_DISCOVERY_NEW,
    SOLAR_NET_ID_SYSTEM,
    SOLAR_NET_RESCAN_TIMER,
    FroniusDeviceInfo,
)
from .coordinator import (
    FroniusCoordinatorBase,
    FroniusInverterUpdateCoordinator,
    FroniusLoggerUpdateCoordinator,
    FroniusMeterUpdateCoordinator,
    FroniusOhmpilotUpdateCoordinator,
    FroniusPowerFlowUpdateCoordinator,
    FroniusStorageUpdateCoordinator,
)

_LOGGER: Final = logging.getLogger(__name__)
PLATFORMS: Final = [Platform.SENSOR]

_FroniusCoordinatorT = TypeVar("_FroniusCoordinatorT", bound=FroniusCoordinatorBase)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up fronius from a config entry."""
    host = entry.data[CONF_HOST]
    fronius = Fronius(async_get_clientsession(hass), host)
    solar_net = FroniusSolarNet(hass, entry, fronius)
    await solar_net.init_devices()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = solar_net
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        solar_net = hass.data[DOMAIN].pop(entry.entry_id)
        while solar_net.cleanup_callbacks:
            solar_net.cleanup_callbacks.pop()()

    return unload_ok


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: ConfigEntry, device_entry: dr.DeviceEntry
) -> bool:
    """Remove a config entry from a device."""
    return True


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
        self.ohmpilot_coordinator: FroniusOhmpilotUpdateCoordinator | None = None
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

        await self._init_devices_inverter()

        self.meter_coordinator = await self._init_optional_coordinator(
            FroniusMeterUpdateCoordinator(
                hass=self.hass,
                solar_net=self,
                logger=_LOGGER,
                name=f"{DOMAIN}_meters_{self.host}",
            )
        )

        self.ohmpilot_coordinator = await self._init_optional_coordinator(
            FroniusOhmpilotUpdateCoordinator(
                hass=self.hass,
                solar_net=self,
                logger=_LOGGER,
                name=f"{DOMAIN}_ohmpilot_{self.host}",
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

        # Setup periodic re-scan
        self.cleanup_callbacks.append(
            async_track_time_interval(
                self.hass,
                self._init_devices_inverter,
                timedelta(minutes=SOLAR_NET_RESCAN_TIMER),
            )
        )

    async def _create_solar_net_device(self) -> DeviceInfo:
        """Create a device for the Fronius SolarNet system."""
        solar_net_device: DeviceInfo = DeviceInfo(
            configuration_url=self.fronius.url,
            identifiers={(DOMAIN, self.solar_net_device_id)},
            manufacturer="Fronius",
            name="SolarNet",
        )
        if self.logger_coordinator:
            _logger_info = self.logger_coordinator.data[SOLAR_NET_ID_SYSTEM]
            # API v0 doesn't provide product_type
            solar_net_device[ATTR_MODEL] = _logger_info.get("product_type", {}).get(
                "value", "Datalogger Web"
            )
            solar_net_device[ATTR_SW_VERSION] = _logger_info["software_version"][
                "value"
            ]

        device_registry = dr.async_get(self.hass)
        device_registry.async_get_or_create(
            config_entry_id=self.config_entry.entry_id,
            **solar_net_device,
        )
        return solar_net_device

    async def _init_devices_inverter(self, _now: datetime | None = None) -> None:
        """Get available inverters and set up coordinators for new found devices."""
        _inverter_infos = await self._get_inverter_infos()

        _LOGGER.debug("Processing inverters for: %s", _inverter_infos)
        for _inverter_info in _inverter_infos:
            _inverter_name = (
                f"{DOMAIN}_inverter_{_inverter_info.solar_net_id}_{self.host}"
            )

            # Add found inverter only not already existing
            if _inverter_info.solar_net_id in [
                inv.inverter_info.solar_net_id for inv in self.inverter_coordinators
            ]:
                continue

            _coordinator = FroniusInverterUpdateCoordinator(
                hass=self.hass,
                solar_net=self,
                logger=_LOGGER,
                name=_inverter_name,
                inverter_info=_inverter_info,
            )
            await _coordinator.async_config_entry_first_refresh()
            self.inverter_coordinators.append(_coordinator)

            # Only for re-scans. Initial setup adds entities through sensor.async_setup_entry
            if self.config_entry.state == ConfigEntryState.LOADED:
                async_dispatcher_send(self.hass, SOLAR_NET_DISCOVERY_NEW, _coordinator)

            _LOGGER.debug(
                "New inverter added (UID: %s)",
                _inverter_info.unique_id,
            )

    async def _get_inverter_infos(self) -> list[FroniusDeviceInfo]:
        """Get information about the inverters in the SolarNet system."""
        inverter_infos: list[FroniusDeviceInfo] = []

        try:
            _inverter_info = await self.fronius.inverter_info()
        except FroniusError as err:
            if self.config_entry.state == ConfigEntryState.LOADED:
                # During a re-scan we will attempt again as per schedule.
                _LOGGER.debug("Re-scan failed for %s", self.host)
                return inverter_infos

            raise ConfigEntryNotReady from err

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
            _LOGGER.debug(
                "Inverter found at %s (Device ID: %s, UID: %s)",
                self.host,
                solar_net_id,
                unique_id,
            )
        return inverter_infos

    @staticmethod
    async def _init_optional_coordinator(
        coordinator: _FroniusCoordinatorT,
    ) -> _FroniusCoordinatorT | None:
        """Initialize an update coordinator and return it if devices are found."""
        try:
            await coordinator.async_config_entry_first_refresh()
        except ConfigEntryNotReady:
            # ConfigEntryNotReady raised form FroniusError / KeyError in
            # DataUpdateCoordinator if request not supported by the Fronius device
            return None
        # if no device for the request is installed an empty dict is returned
        if not coordinator.data:
            return None
        return coordinator
