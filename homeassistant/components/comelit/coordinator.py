"""Support for Comelit."""

from abc import abstractmethod
from datetime import timedelta
from typing import Any, TypeVar

from aiocomelit.api import (
    AlarmDataObject,
    ComelitCommonApi,
    ComeliteSerialBridgeApi,
    ComelitSerialBridgeObject,
    ComelitVedoApi,
    ComelitVedoAreaObject,
    ComelitVedoZoneObject,
)
from aiocomelit.const import (
    BRIDGE,
    CLIMATE,
    COVER,
    IRRIGATION,
    LIGHT,
    OTHER,
    SCENARIO,
    VEDO,
)
from aiocomelit.exceptions import CannotAuthenticate, CannotConnect, CannotRetrieveData
from aiohttp import ClientSession

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import _LOGGER, DOMAIN, SCAN_INTERVAL

type ComelitConfigEntry = ConfigEntry[ComelitBaseCoordinator]


T = TypeVar(
    "T",
    bound=dict[str, dict[int, ComelitSerialBridgeObject]] | AlarmDataObject,
)


class ComelitBaseCoordinator(DataUpdateCoordinator[T]):
    """Base coordinator for Comelit Devices."""

    _hw_version: str
    config_entry: ComelitConfigEntry
    api: ComelitCommonApi

    def __init__(
        self, hass: HomeAssistant, entry: ComelitConfigEntry, device: str, host: str
    ) -> None:
        """Initialize the scanner."""

        self._device = device
        self._host = host

        super().__init__(
            hass=hass,
            logger=_LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}-{host}-coordinator",
            update_interval=timedelta(seconds=SCAN_INTERVAL),
        )
        device_registry = dr.async_get(self.hass)
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, entry.entry_id)},
            model=device,
            name=f"{device} ({self._host})",
            manufacturer="Comelit",
            hw_version=self._hw_version,
        )

    def platform_device_info(
        self,
        object_class: ComelitVedoZoneObject
        | ComelitVedoAreaObject
        | ComelitSerialBridgeObject,
        object_type: str,
    ) -> dr.DeviceInfo:
        """Set platform device info."""

        return dr.DeviceInfo(
            identifiers={
                (
                    DOMAIN,
                    f"{self.config_entry.entry_id}-{object_type}-{object_class.index}",
                )
            },
            via_device=(DOMAIN, self.config_entry.entry_id),
            name=object_class.name,
            model=f"{self._device} {object_type}",
            manufacturer="Comelit",
            hw_version=self._hw_version,
        )

    async def _async_update_data(self) -> T:
        """Update device data."""
        _LOGGER.debug("Polling Comelit %s host: %s", self._device, self._host)
        try:
            await self.api.login()
            return await self._async_update_system_data()
        except (CannotConnect, CannotRetrieveData) as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"error": repr(err)},
            ) from err
        except CannotAuthenticate as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_authenticate",
            ) from err

    @abstractmethod
    async def _async_update_system_data(self) -> T:
        """Class method for updating data."""

    async def _async_remove_stale_devices(
        self,
        previous_list: dict[int, Any],
        current_list: dict[int, Any],
        dev_type: str,
    ) -> None:
        """Remove stale devices."""
        device_registry = dr.async_get(self.hass)

        for i in range(max(previous_list.keys(), default=0) + 1):
            if previous_list.get(i) and not current_list.get(i):
                _LOGGER.debug(
                    "Detected change in %s devices: index %s removed",
                    dev_type,
                    i,
                )
                identifier = f"{self.config_entry.entry_id}-{dev_type}-{i}"
                device = device_registry.async_get_device(
                    identifiers={(DOMAIN, identifier)}
                )
                if device:
                    device_registry.async_update_device(
                        device_id=device.id,
                        remove_config_entry_id=self.config_entry.entry_id,
                    )


class ComelitSerialBridge(
    ComelitBaseCoordinator[dict[str, dict[int, ComelitSerialBridgeObject]]]
):
    """Queries Comelit Serial Bridge."""

    _hw_version = "20003101"
    api: ComeliteSerialBridgeApi

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ComelitConfigEntry,
        host: str,
        port: int,
        pin: int,
        session: ClientSession,
    ) -> None:
        """Initialize the scanner."""
        self.api = ComeliteSerialBridgeApi(host, port, pin, session)
        super().__init__(hass, entry, BRIDGE, host)
        self.previous_devices: dict[str, dict[int, ComelitSerialBridgeObject]] = {}

    async def _async_update_system_data(
        self,
    ) -> dict[str, dict[int, ComelitSerialBridgeObject]]:
        """Specific method for updating data."""
        data = await self.api.get_all_devices()

        if self.previous_devices:
            for dev_type in (CLIMATE, COVER, LIGHT, IRRIGATION, OTHER, SCENARIO):
                await self._async_remove_stale_devices(
                    self.previous_devices[dev_type], data[dev_type], dev_type
                )

        self.previous_devices = data.copy()
        return data


class ComelitVedoSystem(ComelitBaseCoordinator[AlarmDataObject]):
    """Queries Comelit VEDO system."""

    _hw_version = "VEDO IP"
    api: ComelitVedoApi

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ComelitConfigEntry,
        host: str,
        port: int,
        pin: int,
        session: ClientSession,
    ) -> None:
        """Initialize the scanner."""
        self.api = ComelitVedoApi(host, port, pin, session)
        super().__init__(hass, entry, VEDO, host)

    async def _async_update_system_data(
        self,
    ) -> AlarmDataObject:
        """Specific method for updating data."""
        data = await self.api.get_all_areas_and_zones()

        if self.data:
            for obj_type in ("alarm_areas", "alarm_zones"):
                await self._async_remove_stale_devices(
                    self.data[obj_type],
                    data[obj_type],
                    "area" if obj_type == "alarm_areas" else "zone",
                )

        return data
