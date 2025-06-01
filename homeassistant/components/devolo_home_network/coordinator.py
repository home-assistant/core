"""Base coordinator."""

from asyncio import Semaphore
from dataclasses import dataclass
from datetime import timedelta
from logging import Logger
from typing import Any

from devolo_plc_api import Device
from devolo_plc_api.device_api import (
    ConnectedStationInfo,
    NeighborAPInfo,
    UpdateFirmwareCheck,
    WifiGuestAccessGet,
)
from devolo_plc_api.exceptions.device import DevicePasswordProtected, DeviceUnavailable
from devolo_plc_api.plcnet_api import LogicalNetwork

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONNECTED_PLC_DEVICES,
    CONNECTED_WIFI_CLIENTS,
    DOMAIN,
    FIRMWARE_UPDATE_INTERVAL,
    LAST_RESTART,
    LONG_UPDATE_INTERVAL,
    NEIGHBORING_WIFI_NETWORKS,
    REGULAR_FIRMWARE,
    SHORT_UPDATE_INTERVAL,
    SWITCH_GUEST_WIFI,
    SWITCH_LEDS,
)

SEMAPHORE = Semaphore(1)

type DevoloHomeNetworkConfigEntry = ConfigEntry[DevoloHomeNetworkData]


class DevoloDataUpdateCoordinator[_DataT](DataUpdateCoordinator[_DataT]):
    """Class to manage fetching data from devolo Home Network devices."""

    def __init__(
        self,
        hass: HomeAssistant,
        logger: Logger,
        *,
        config_entry: DevoloHomeNetworkConfigEntry,
        name: str,
        update_interval: timedelta | None = None,
    ) -> None:
        """Initialize global data updater."""
        self.device = config_entry.runtime_data.device
        super().__init__(
            hass,
            logger,
            config_entry=config_entry,
            name=name,
            update_interval=update_interval,
        )

    async def _async_update_data(self) -> _DataT:
        """Fetch the latest data from the source."""
        self.update_sw_version()
        async with SEMAPHORE:
            try:
                return await super()._async_update_data()
            except DeviceUnavailable as err:
                raise UpdateFailed(
                    translation_domain=DOMAIN,
                    translation_key="update_failed",
                    translation_placeholders={"error": str(err)},
                ) from err
            except DevicePasswordProtected as err:
                raise ConfigEntryAuthFailed(
                    translation_domain=DOMAIN, translation_key="password_wrong"
                ) from err

    @callback
    def update_sw_version(self) -> None:
        """Update device registry with new firmware version, if it changed at runtime."""
        device_registry = dr.async_get(self.hass)
        if (
            device_entry := device_registry.async_get_device(
                identifiers={(DOMAIN, self.device.serial_number)}
            )
        ) and device_entry.sw_version != self.device.firmware_version:
            device_registry.async_update_device(
                device_id=device_entry.id, sw_version=self.device.firmware_version
            )


class DevoloFirmwareUpdateCoordinator(DevoloDataUpdateCoordinator[UpdateFirmwareCheck]):
    """Class to manage fetching data from the UpdateFirmwareCheck endpoint."""

    def __init__(
        self,
        hass: HomeAssistant,
        logger: Logger,
        *,
        config_entry: ConfigEntry,
        name: str = REGULAR_FIRMWARE,
        update_interval: timedelta | None = FIRMWARE_UPDATE_INTERVAL,
    ) -> None:
        """Initialize global data updater."""
        super().__init__(
            hass,
            logger,
            config_entry=config_entry,
            name=name,
            update_interval=update_interval,
        )
        self.update_method = self.async_update_firmware_available

    async def async_update_firmware_available(self) -> UpdateFirmwareCheck:
        """Fetch data from API endpoint."""
        assert self.device.device
        return await self.device.device.async_check_firmware_available()


class DevoloLedSettingsGetCoordinator(DevoloDataUpdateCoordinator[bool]):
    """Class to manage fetching data from the LedSettingsGet endpoint."""

    def __init__(
        self,
        hass: HomeAssistant,
        logger: Logger,
        *,
        config_entry: ConfigEntry,
        name: str = SWITCH_LEDS,
        update_interval: timedelta | None = SHORT_UPDATE_INTERVAL,
    ) -> None:
        """Initialize global data updater."""
        super().__init__(
            hass,
            logger,
            config_entry=config_entry,
            name=name,
            update_interval=update_interval,
        )
        self.update_method = self.async_update_led_status

    async def async_update_led_status(self) -> bool:
        """Fetch data from API endpoint."""
        assert self.device.device
        return await self.device.device.async_get_led_setting()


class DevoloLogicalNetworkCoordinator(DevoloDataUpdateCoordinator[LogicalNetwork]):
    """Class to manage fetching data from the GetNetworkOverview endpoint."""

    def __init__(
        self,
        hass: HomeAssistant,
        logger: Logger,
        *,
        config_entry: ConfigEntry,
        name: str = CONNECTED_PLC_DEVICES,
        update_interval: timedelta | None = LONG_UPDATE_INTERVAL,
    ) -> None:
        """Initialize global data updater."""
        super().__init__(
            hass,
            logger,
            config_entry=config_entry,
            name=name,
            update_interval=update_interval,
        )
        self.update_method = self.async_update_connected_plc_devices

    async def async_update_connected_plc_devices(self) -> LogicalNetwork:
        """Fetch data from API endpoint."""
        assert self.device.plcnet
        return await self.device.plcnet.async_get_network_overview()


class DevoloUptimeGetCoordinator(DevoloDataUpdateCoordinator[int]):
    """Class to manage fetching data from the UptimeGet endpoint."""

    def __init__(
        self,
        hass: HomeAssistant,
        logger: Logger,
        *,
        config_entry: ConfigEntry,
        name: str = LAST_RESTART,
        update_interval: timedelta | None = SHORT_UPDATE_INTERVAL,
    ) -> None:
        """Initialize global data updater."""
        super().__init__(
            hass,
            logger,
            config_entry=config_entry,
            name=name,
            update_interval=update_interval,
        )
        self.update_method = self.async_update_last_restart

    async def async_update_last_restart(self) -> int:
        """Fetch data from API endpoint."""
        assert self.device.device
        return await self.device.device.async_uptime()


class DevoloWifiConnectedStationsGetCoordinator(
    DevoloDataUpdateCoordinator[list[ConnectedStationInfo]]
):
    """Class to manage fetching data from the WifiGuestAccessGet endpoint."""

    def __init__(
        self,
        hass: HomeAssistant,
        logger: Logger,
        *,
        config_entry: ConfigEntry,
        name: str = CONNECTED_WIFI_CLIENTS,
        update_interval: timedelta | None = SHORT_UPDATE_INTERVAL,
    ) -> None:
        """Initialize global data updater."""
        super().__init__(
            hass,
            logger,
            config_entry=config_entry,
            name=name,
            update_interval=update_interval,
        )
        self.update_method = self.async_get_wifi_connected_station

    async def async_get_wifi_connected_station(self) -> list[ConnectedStationInfo]:
        """Fetch data from API endpoint."""
        assert self.device.device
        return await self.device.device.async_get_wifi_connected_station()


class DevoloWifiGuestAccessGetCoordinator(
    DevoloDataUpdateCoordinator[WifiGuestAccessGet]
):
    """Class to manage fetching data from the WifiGuestAccessGet endpoint."""

    def __init__(
        self,
        hass: HomeAssistant,
        logger: Logger,
        *,
        config_entry: ConfigEntry,
        name: str = SWITCH_GUEST_WIFI,
        update_interval: timedelta | None = SHORT_UPDATE_INTERVAL,
    ) -> None:
        """Initialize global data updater."""
        super().__init__(
            hass,
            logger,
            config_entry=config_entry,
            name=name,
            update_interval=update_interval,
        )
        self.update_method = self.async_update_guest_wifi_status

    async def async_update_guest_wifi_status(self) -> WifiGuestAccessGet:
        """Fetch data from API endpoint."""
        assert self.device.device
        return await self.device.device.async_get_wifi_guest_access()


class DevoloWifiNeighborAPsGetCoordinator(
    DevoloDataUpdateCoordinator[list[NeighborAPInfo]]
):
    """Class to manage fetching data from the WifiNeighborAPsGet endpoint."""

    def __init__(
        self,
        hass: HomeAssistant,
        logger: Logger,
        *,
        config_entry: ConfigEntry,
        name: str = NEIGHBORING_WIFI_NETWORKS,
        update_interval: timedelta | None = LONG_UPDATE_INTERVAL,
    ) -> None:
        """Initialize global data updater."""
        super().__init__(
            hass,
            logger,
            config_entry=config_entry,
            name=name,
            update_interval=update_interval,
        )
        self.update_method = self.async_update_wifi_neighbor_access_points

    async def async_update_wifi_neighbor_access_points(self) -> list[NeighborAPInfo]:
        """Fetch data from API endpoint."""
        assert self.device.device
        return await self.device.device.async_get_wifi_neighbor_access_points()


@dataclass
class DevoloHomeNetworkData:
    """The devolo Home Network data."""

    device: Device
    coordinators: dict[str, DevoloDataUpdateCoordinator[Any]]
