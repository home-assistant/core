"""Device discovery for a Fronius SolarNet system."""

import asyncio
from datetime import datetime, timedelta
import logging
from typing import Any, Final

from fronius_solarapi import FroniusError, FroniusSolarApi

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    DOMAIN,
    SOLAR_NET_ID_SYSTEM,
    SOLAR_NET_RESCAN_TIMER,
    FroniusDeviceInfo,
    discovery_signal,
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
from .modbus import FroniusModbus

_LOGGER: Final = logging.getLogger(__name__)


class FroniusSolarNet:
    """Discover the devices of a SolarNet system and hold their coordinators."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, fronius: FroniusSolarApi
    ) -> None:
        """Initialize FroniusSolarNet class."""
        self.hass = hass
        self.config_entry = entry
        self.coordinator_lock = asyncio.Lock()
        self.fronius = fronius
        self.host: str = entry.data[CONF_HOST]
        # entry.unique_id is either logger uid or first inverter
        # uid if no logger available prepended by "solar_net_"
        # to have individual device for whole system (power_flow)
        self.solar_net_device_id = f"solar_net_{entry.unique_id}"
        self.system_device_info: DeviceInfo | None = None

        self.inverter_coordinators: list[FroniusInverterUpdateCoordinator] = []
        self.logger_coordinator: FroniusLoggerUpdateCoordinator | None = None
        self.meter_coordinator: FroniusMeterUpdateCoordinator | None = None
        self.ohmpilot_coordinator: FroniusOhmpilotUpdateCoordinator | None = None
        self.power_flow_coordinator: FroniusPowerFlowUpdateCoordinator | None = None
        self.storage_coordinator: FroniusStorageUpdateCoordinator | None = None

        self.modbus = FroniusModbus(hass, entry, self)

    @property
    def coordinators(self) -> list[FroniusCoordinatorBase[Any]]:
        """Return the coordinators set up so far."""
        optional = (
            self.logger_coordinator,
            self.meter_coordinator,
            self.ohmpilot_coordinator,
            self.power_flow_coordinator,
            self.storage_coordinator,
        )
        return [
            *self.inverter_coordinators,
            *self.modbus.inverter_coordinators,
            *(coordinator for coordinator in optional if coordinator is not None),
            *self.modbus.settings_coordinators,
        ]

    async def init_devices(self) -> None:
        """Initialize DataUpdateCoordinators for SolarNet devices."""
        if self.config_entry.data["is_logger"]:
            self.logger_coordinator = FroniusLoggerUpdateCoordinator(
                hass=self.hass,
                solar_net=self,
                logger=_LOGGER,
                name=f"{DOMAIN}_logger_{self.host}",
                config_entry=self.config_entry,
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
                config_entry=self.config_entry,
            )
        )

        self.ohmpilot_coordinator = await self._init_optional_coordinator(
            FroniusOhmpilotUpdateCoordinator(
                hass=self.hass,
                solar_net=self,
                logger=_LOGGER,
                name=f"{DOMAIN}_ohmpilot_{self.host}",
                config_entry=self.config_entry,
            )
        )

        self.power_flow_coordinator = await self._init_optional_coordinator(
            FroniusPowerFlowUpdateCoordinator(
                hass=self.hass,
                solar_net=self,
                logger=_LOGGER,
                name=f"{DOMAIN}_power_flow_{self.host}",
                config_entry=self.config_entry,
            )
        )

        self.storage_coordinator = await self._init_optional_coordinator(
            FroniusStorageUpdateCoordinator(
                hass=self.hass,
                solar_net=self,
                logger=_LOGGER,
                name=f"{DOMAIN}_storages_{self.host}",
                config_entry=self.config_entry,
            )
        )

        # Setup periodic re-scan
        self.config_entry.async_on_unload(
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
            # API v0 doesn't provide a product id
            solar_net_device.model = _logger_info.product_id or "Datalogger Web"
            solar_net_device.sw_version = _logger_info.software_version

        device_registry = dr.async_get(self.hass)
        device_registry.async_get_or_create_from_info(
            config_entry_id=self.config_entry.entry_id,
            device_info=solar_net_device,
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
                config_entry=self.config_entry,
            )
            if self.config_entry.state is ConfigEntryState.LOADED:
                await _coordinator.async_refresh()
            else:
                await _coordinator.async_config_entry_first_refresh()
            self.inverter_coordinators.append(_coordinator)

            # Only for re-scans. Initial setup adds entities
            # through sensor.async_setup_entry
            if self.config_entry.state is ConfigEntryState.LOADED:
                async_dispatcher_send(
                    self.hass,
                    discovery_signal(self.config_entry.entry_id),
                    _coordinator,
                )

            _LOGGER.debug(
                "New inverter added (UID: %s)",
                _inverter_info.unique_id,
            )

        # an inverter that was asleep answers nothing, so retry the ones
        # still without Modbus data on every re-scan
        for inverter_coordinator in self.inverter_coordinators:
            await self.modbus.async_init_inverter(inverter_coordinator.inverter_info)

    async def _get_inverter_infos(self) -> list[FroniusDeviceInfo]:
        """Get information about the inverters in the SolarNet system."""
        inverter_infos: list[FroniusDeviceInfo] = []

        try:
            response = await self.fronius.inverter_info()
        except FroniusError as err:
            if self.config_entry.state is ConfigEntryState.LOADED:
                # During a re-scan we will attempt again as per schedule.
                _LOGGER.debug("Re-scan failed for %s", self.host)
                return inverter_infos

            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="entry_cannot_connect",
                translation_placeholders={
                    "host": self.host,
                    "fronius_error": str(err),
                },
            ) from err

        for solar_net_id, inverter in response.data.items():
            unique_id = inverter.unique_id
            model = inverter.model
            device_info = DeviceInfo(
                identifiers={(DOMAIN, unique_id)},
                manufacturer=model.manufacturer if model else "Fronius",
                model=model.model if model else str(inverter.device_type),
                name=inverter.custom_name,
                via_device_id=dr.async_get_device_id_by_identifier(
                    self.hass,
                    (DOMAIN, self.solar_net_device_id),
                    config_entry_id=self.config_entry.entry_id,
                ),
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
    async def _init_optional_coordinator[_FroniusCoordinatorT: FroniusCoordinatorBase](
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
