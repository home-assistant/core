"""The Fronius integration."""
from __future__ import annotations

from datetime import timedelta
import logging

from pyfronius import Fronius

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN
from .coordinator import FroniusMeterUpdateCoordinator, FroniusStorageUpdateCoordinator

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
        self.meter_coordinator: FroniusMeterUpdateCoordinator | None = None
        self.storage_coordinator: FroniusStorageUpdateCoordinator | None = None

    @callback
    def _init_bridge(self) -> Fronius:
        """Initialize Fronius API."""
        session = async_get_clientsession(self.hass)
        return Fronius(session, self.url)

    async def init_devices(self):
        """Initialize DataUpdateCoordinators for SolarNet devices."""
        # inverter_count = await self._get_inverter_unique_ids()
        self.meter_coordinator = await self.init_optional_coordinator(
            FroniusMeterUpdateCoordinator(
                hass=self.hass,
                logger=_LOGGER,
                name=f"{DOMAIN}_meters",
                update_interval=self.update_interval,
                update_method=self.bridge.current_system_meter_data,
            )
        )
        self.storage_coordinator = await self.init_optional_coordinator(
            FroniusStorageUpdateCoordinator(
                hass=self.hass,
                logger=_LOGGER,
                name=f"{DOMAIN}_storages",
                update_interval=self.update_interval,
                update_method=self.bridge.current_system_storage_data,
            )
        )

        # power_flow
        # logger_info

    # async def _get_inverter_unique_ids(self) -> int:
    #     try:
    #         inverters = await self.bridge.inverter_info()
    #     except FroniusError as err:
    #         _LOGGER.warning(err)
    #     else:
    #         for solar_net_id, inverter in inverters["inverters"].items():
    #             device = SolarNetDevice(
    #                 device_type=SolarNetDeviceType.INVERTER,
    #                 manufacturer="Fronius",
    #                 model=inverter["custom_name"]["value"],
    #                 solar_net_id=inverter["device_id"]["value"],
    #                 unique_id=inverter["unique_id"]["value"],
    #             )
    #             self.solar_net_devices.append(device)
    #             self.adapters.append(FroniusInverterDevice(self, device))
    #         return len(inverters["inverters"])
    #     print(f"solar_net\n{self.solar_net_devices}")

    @staticmethod
    async def init_optional_coordinator(
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
