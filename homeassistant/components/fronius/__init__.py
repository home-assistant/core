"""The Fronius integration."""
from __future__ import annotations

from datetime import timedelta
import logging

from pyfronius import Fronius, FroniusError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    SOLAR_NET_ID_SYSTEM,
    FroniusDeviceInfo,
)
from .coordinator import (
    FroniusInverterUpdateCoordinator,
    FroniusMeterUpdateCoordinator,
    FroniusPowerFlowUpdateCoordinator,
    FroniusStorageUpdateCoordinator,
)

_LOGGER = logging.getLogger(__name__)
PLATFORMS: list[str] = ["sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up fronius from a config entry."""
    fronius = FroniusSolarNet(hass, entry)
    # TODO: does this retry - only for inverters/logger - when ConfigEntryNotReady
    await fronius.init_devices()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = fronius
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class FroniusSolarNet:
    """The FroniusSolarNet class routes received values to sensor entities."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize FroniusSolarNet class."""
        self.hass = hass
        self.config_entry_id = entry.entry_id
        self.host: str = entry.data[CONF_HOST]
        # entry.unique_id is either logger uid or first inverter uid if no logger available
        # prepended by "solar_net_" to have individual device for whole system (power_flow)
        self.solar_net_device_id = f"solar_net_{entry.unique_id}"
        self.update_interval = timedelta(seconds=DEFAULT_UPDATE_INTERVAL)
        self._has_logger: bool = entry.data["is_logger"]

        self.fronius: Fronius = self._init_bridge()
        self.inverter_coordinators: list[FroniusInverterUpdateCoordinator] = []
        self.meter_coordinator: FroniusMeterUpdateCoordinator | None = None
        self.power_flow_coordinator: FroniusPowerFlowUpdateCoordinator | None = None
        self.storage_coordinator: FroniusStorageUpdateCoordinator | None = None

    @callback
    def _init_bridge(self) -> Fronius:
        """Initialize Fronius API."""
        session = async_get_clientsession(self.hass)
        return Fronius(session, self.host)

    async def init_devices(self):
        """Initialize DataUpdateCoordinators for SolarNet devices."""
        solar_net_device_info = await self._create_solar_net_device()
        _inverter_infos = await self._get_inverter_infos()
        for inverter_info in _inverter_infos:
            coordinator = FroniusInverterUpdateCoordinator(
                hass=self.hass,
                solar_net=self,
                logger=_LOGGER,
                name=f"{DOMAIN}_inverter_{inverter_info.solar_net_id}_{self.host}",
                update_interval=self.update_interval,
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
                update_interval=self.update_interval,
            )
        )

        self.power_flow_coordinator = FroniusPowerFlowUpdateCoordinator(
            hass=self.hass,
            solar_net=self,
            logger=_LOGGER,
            name=f"{DOMAIN}_power_flow_{self.host}",
            update_interval=self.update_interval,
            power_flow_info=solar_net_device_info,
        )
        await self.power_flow_coordinator.async_config_entry_first_refresh()

        self.storage_coordinator = await self._init_optional_coordinator(
            FroniusStorageUpdateCoordinator(
                hass=self.hass,
                solar_net=self,
                logger=_LOGGER,
                name=f"{DOMAIN}_storages_{self.host}",
                update_interval=self.update_interval,
            )
        )

    async def _create_solar_net_device(self) -> FroniusDeviceInfo:
        """Create a device for the Fronius SolarNet system."""
        solar_net_device: DeviceInfo = DeviceInfo(
            name="SolarNet",
            identifiers={(DOMAIN, self.solar_net_device_id)},
            manufacturer="Fronius",
        )
        if self._has_logger:
            try:
                _logger_info = await self.fronius.current_logger_info()
            except FroniusError as err:
                raise ConfigEntryNotReady from err
            solar_net_device["model"] = _logger_info["product_type"]["value"]
            solar_net_device["sw_version"] = _logger_info["software_version"]["value"]

        device_registry = await dr.async_get_registry(self.hass)
        device_registry.async_get_or_create(
            config_entry_id=self.config_entry_id,
            **solar_net_device,
        )
        return FroniusDeviceInfo(
            device_info=solar_net_device,
            solar_net_id=SOLAR_NET_ID_SYSTEM,
            unique_id=self.solar_net_device_id,
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
            device_info = DeviceInfo(
                name=inverter.get("custom_name", {}).get("value"),
                identifiers={(DOMAIN, unique_id)},
                manufacturer=inverter["device_type"].get("manufacturer", "Fronius"),
                model=inverter["device_type"].get(
                    "model", inverter["device_type"]["value"]
                ),
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
        coordinator: DataUpdateCoordinator,
    ) -> DataUpdateCoordinator | None:
        """Initialize an update coordinator and return it if devices are found."""
        try:
            await coordinator.async_config_entry_first_refresh()
        except ConfigEntryNotReady:
            # TODO: do we have to clean up the coordinator if not used?
            return None
        # keep coordinator only if devices are found
        # else ConfigEntryNotReady raised form KeyError
        # in FroniusMeterUpdateCoordinator._get_fronius_device_data
        return coordinator
