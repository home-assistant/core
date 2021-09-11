"""The Fronius integration."""
from __future__ import annotations

from datetime import timedelta
import logging

from pyfronius import Fronius, FroniusError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, FroniusDeviceInfo
from .coordinator import (
    FroniusInverterUpdateCoordinator,
    FroniusMeterUpdateCoordinator,
    FroniusPowerFlowUpdateCoordinator,
    FroniusStorageUpdateCoordinator,
)

_LOGGER = logging.getLogger(__name__)
PLATFORMS: list[str] = ["sensor"]
# TODO: add option flow to configure individual update intervals
DEFAULT_UPDATE_INTERVAL = 60


# TODO: add import for yaml config - see eg. `awair` integration
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
        self.bridge_uid: str = entry.unique_id  # type: ignore[assignment]
        self.update_interval = timedelta(seconds=DEFAULT_UPDATE_INTERVAL)
        self.url: str = entry.data[CONF_HOST]
        self._has_logger: bool = entry.data["is_logger"]

        self.bridge: Fronius = self._init_bridge()
        self.inverter_coordinators: list[FroniusInverterUpdateCoordinator] = []
        self.meter_coordinator: FroniusMeterUpdateCoordinator | None = None
        self.power_flow_coordinator: FroniusPowerFlowUpdateCoordinator | None = None
        self.storage_coordinator: FroniusStorageUpdateCoordinator | None = None

    @callback
    def _init_bridge(self) -> Fronius:
        """Initialize Fronius API."""
        session = async_get_clientsession(self.hass)
        return Fronius(session, self.url)

    async def init_devices(self):
        """Initialize DataUpdateCoordinators for SolarNet devices."""
        _inverter_infos = await self._get_inverter_infos()
        for inverter_info in _inverter_infos:
            coordinator = FroniusInverterUpdateCoordinator(
                hass=self.hass,
                fronius=self.bridge,
                logger=_LOGGER,
                name=f"{DOMAIN}_inverter_{inverter_info.solar_net_id}_{self.url}",
                update_interval=self.update_interval,
                inverter_info=inverter_info,
            )
            await coordinator.async_config_entry_first_refresh()
            self.inverter_coordinators.append(coordinator)

        self.meter_coordinator = await self._init_optional_coordinator(
            FroniusMeterUpdateCoordinator(
                hass=self.hass,
                fronius=self.bridge,
                logger=_LOGGER,
                name=f"{DOMAIN}_meters_{self.url}",
                update_interval=self.update_interval,
            )
        )
        # TODO: use logger as device if available or create SolarNet device
        # instead of adding to first inverter
        power_flow_info = _inverter_infos[0]
        self.power_flow_coordinator = FroniusPowerFlowUpdateCoordinator(
            hass=self.hass,
            fronius=self.bridge,
            logger=_LOGGER,
            name=f"{DOMAIN}_power_flow_{self.url}",
            update_interval=self.update_interval,
            power_flow_info=power_flow_info,
        )
        await self.power_flow_coordinator.async_config_entry_first_refresh()

        self.storage_coordinator = await self._init_optional_coordinator(
            FroniusStorageUpdateCoordinator(
                hass=self.hass,
                fronius=self.bridge,
                logger=_LOGGER,
                name=f"{DOMAIN}_storages_{self.url}",
                update_interval=self.update_interval,
            )
        )
        # logger_info

    async def _get_inverter_infos(self) -> list[FroniusDeviceInfo]:
        """Get information about the inverters in the SolarNet system."""
        try:
            _inverter_info = await self.bridge.inverter_info()
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
                # TODO: via_device? entry_type?
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
