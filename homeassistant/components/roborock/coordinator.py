"""Roborock Coordinator."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from typing import Any, TypeVar

from propcache.api import cached_property
from roborock.data import RoborockCategory
from roborock.devices.device import RoborockDevice
from roborock.devices.traits.a01 import DyadApi, ZeoApi
from roborock.devices.traits.v1 import PropertiesApi
from roborock.exceptions import RoborockDeviceBusy, RoborockException
from roborock.roborock_message import RoborockDyadDataProtocol, RoborockZeoProtocol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_CONNECTIONS
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util, slugify

from .const import (
    A01_UPDATE_INTERVAL,
    DOMAIN,
    IMAGE_CACHE_INTERVAL,
    V1_CLOUD_IN_CLEANING_INTERVAL,
    V1_CLOUD_NOT_CLEANING_INTERVAL,
    V1_LOCAL_IN_CLEANING_INTERVAL,
    V1_LOCAL_NOT_CLEANING_INTERVAL,
)
from .models import DeviceState

SCAN_INTERVAL = timedelta(seconds=30)

_LOGGER = logging.getLogger(__name__)


@dataclass
class RoborockCoordinators:
    """Roborock coordinators type."""

    v1: list[RoborockDataUpdateCoordinator]
    a01: list[RoborockDataUpdateCoordinatorA01]

    def values(
        self,
    ) -> list[RoborockDataUpdateCoordinator | RoborockDataUpdateCoordinatorA01]:
        """Return all coordinators."""
        return self.v1 + self.a01


type RoborockConfigEntry = ConfigEntry[RoborockCoordinators]


class RoborockDataUpdateCoordinator(DataUpdateCoordinator[DeviceState]):
    """Class to manage fetching data from the API."""

    config_entry: RoborockConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: RoborockConfigEntry,
        device: RoborockDevice,
        properties_api: PropertiesApi,
    ) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            # Update interval is adjusted in `_async_update_data`
            update_interval=V1_LOCAL_NOT_CLEANING_INTERVAL,
        )
        self._device = device
        self.properties_api = properties_api
        self.device_info = DeviceInfo(
            name=self._device.device_info.name,
            identifiers={(DOMAIN, self.duid)},
            manufacturer="Roborock",
            model=self._device.product.model,
            model_id=self._device.product.model,
            sw_version=self._device.device_info.fv,
        )
        if mac := properties_api.network_info.mac:
            self.device_info[ATTR_CONNECTIONS] = {
                (dr.CONNECTION_NETWORK_MAC, dr.format_mac(mac))
            }
        self.last_update_state: str | None = None
        # Keep track of last attempt to refresh maps/rooms to know when to try again.
        self._last_home_update_attempt: datetime | None = None
        self.last_home_update: datetime | None = None

    @cached_property
    def dock_device_info(self) -> DeviceInfo:
        """Gets the device info for the dock.

        This must happen after the coordinator does the first update.
        Which will be the case when this is called.
        """
        dock_type = self.properties_api.status.dock_type
        return DeviceInfo(
            name=f"{self._device.device_info.name} Dock",
            identifiers={(DOMAIN, f"{self.duid}_dock")},
            manufacturer="Roborock",
            model=f"{self._device.product.model} Dock",
            model_id=str(dock_type.value) if dock_type is not None else "Unknown",
            sw_version=self._device.device_info.fv,
        )

    async def _async_setup(self) -> None:
        """Set up the coordinator."""
        await self.properties_api.status.refresh()

        self._last_home_update_attempt = dt_util.utcnow()
        try:
            await self.properties_api.home.discover_home()
        except RoborockDeviceBusy:
            _LOGGER.info("Home discovery skipped while device is busy/cleaning")
        else:
            self.last_home_update = dt_util.utcnow()

    async def update_map(self) -> None:
        """Update the currently selected map."""
        try:
            await self.properties_api.home.discover_home()
            await self.properties_api.home.refresh()
        except RoborockException as ex:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="map_failure",
            ) from ex
        else:
            self.last_home_update = dt_util.utcnow()

    async def async_shutdown(self) -> None:
        """Shutdown the coordinator."""
        await super().async_shutdown()

    async def _update_device_prop(self) -> None:
        """Update device properties."""
        await _refresh_traits(
            [
                trait
                for trait in (
                    self.properties_api.status,
                    self.properties_api.consumables,
                    self.properties_api.clean_summary,
                    self.properties_api.dnd,
                    self.properties_api.dust_collection_mode,
                    self.properties_api.wash_towel_mode,
                    self.properties_api.smart_wash_params,
                    self.properties_api.sound_volume,
                    self.properties_api.child_lock,
                    self.properties_api.dust_collection_mode,
                    self.properties_api.flow_led_status,
                    self.properties_api.valley_electricity_timer,
                )
                if trait is not None
            ]
        )
        _LOGGER.debug("Updated device properties")

    async def _async_update_data(self) -> DeviceState:
        """Update data via library."""
        try:
            # Update device props and standard api information
            await self._update_device_prop()
        except RoborockException as ex:
            _LOGGER.debug("Failed to update data: %s", ex)
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_data_fail",
            ) from ex

        # If the vacuum is currently cleaning and it has been IMAGE_CACHE_INTERVAL
        # since the last map update, you can update the map.
        new_status = self.properties_api.status
        if (
            new_status.in_cleaning
            and (
                self._last_home_update_attempt is None
                or (dt_util.utcnow() - self._last_home_update_attempt)
                > IMAGE_CACHE_INTERVAL
            )
        ) or self.last_update_state != new_status.state_name:
            self._last_home_update_attempt = dt_util.utcnow()
            try:
                await self.update_map()
            except HomeAssistantError as err:
                _LOGGER.debug("Failed to update map: %s", err)

        if self.properties_api.status.in_cleaning:
            if self._device.is_local_connected:
                self.update_interval = V1_LOCAL_IN_CLEANING_INTERVAL
            else:
                self.update_interval = V1_CLOUD_IN_CLEANING_INTERVAL
        elif self._device.is_local_connected:
            self.update_interval = V1_LOCAL_NOT_CLEANING_INTERVAL
        else:
            self.update_interval = V1_CLOUD_NOT_CLEANING_INTERVAL
        self.last_update_state = self.properties_api.status.state_name
        return DeviceState(
            status=self.properties_api.status,
            dnd_timer=self.properties_api.dnd,
            consumable=self.properties_api.consumables,
            clean_summary=self.properties_api.clean_summary,
        )

    @cached_property
    def duid(self) -> str:
        """Get the unique id of the device as specified by Roborock."""
        return self._device.duid

    @cached_property
    def duid_slug(self) -> str:
        """Get the slug of the duid."""
        return slugify(self.duid)

    @property
    def device(self) -> RoborockDevice:
        """Get the RoborockDevice."""
        return self._device


async def _refresh_traits(traits: list[Any]) -> None:
    """Refresh multiple traits concurrently."""
    for trait in traits:
        try:
            # await asyncio.gather(*[trait.refresh() for trait in traits])
            await trait.refresh()
        except RoborockException as ex:
            _LOGGER.debug(
                "Failed to update data (%s): %s", trait.__class__.__name__, ex
            )
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_data_fail",
            ) from ex


_V = TypeVar("_V", bound=RoborockDyadDataProtocol | RoborockZeoProtocol)


class RoborockDataUpdateCoordinatorA01(DataUpdateCoordinator[dict[_V, StateType]]):
    """Class to manage fetching data from the API for A01 devices."""

    config_entry: RoborockConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: RoborockConfigEntry,
        device: RoborockDevice,
    ) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=A01_UPDATE_INTERVAL,
        )
        self._device = device
        self.device_info = DeviceInfo(
            name=device.name,
            identifiers={(DOMAIN, device.duid)},
            manufacturer="Roborock",
            model=device.product.model,
            sw_version=device.device_info.fv,
        )
        self.request_protocols: list[_V] = []

    @cached_property
    def duid(self) -> str:
        """Get the unique id of the device as specified by Roborock."""
        return self._device.duid

    @cached_property
    def duid_slug(self) -> str:
        """Get the slug of the duid."""
        return slugify(self.duid)

    @property
    def device(self) -> RoborockDevice:
        """Get the RoborockDevice."""
        return self._device


class RoborockZeoUpdateCoordinator(
    RoborockDataUpdateCoordinatorA01[RoborockZeoProtocol]
):
    """Coordinator for Zeo devices."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: RoborockConfigEntry,
        device: RoborockDevice,
        api: ZeoApi,
    ) -> None:
        """Initialize."""
        super().__init__(hass, config_entry, device)
        self.api = api
        self.request_protocols: list[RoborockZeoProtocol] = []
        if device.product.category == RoborockCategory.WASHING_MACHINE:
            self.request_protocols = [
                RoborockZeoProtocol.STATE,
                RoborockZeoProtocol.COUNTDOWN,
                RoborockZeoProtocol.WASHING_LEFT,
                RoborockZeoProtocol.ERROR,
            ]
        else:
            _LOGGER.warning("The device you added is not yet supported")

    async def _async_update_data(
        self,
    ) -> dict[RoborockZeoProtocol, StateType]:
        return await self.api.query_values(self.request_protocols)


class RoborockDyadUpdateCoordinator(
    RoborockDataUpdateCoordinatorA01[RoborockDyadDataProtocol]
):
    """Coordinator for Dyad devices."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: RoborockConfigEntry,
        device: RoborockDevice,
        api: DyadApi,
    ) -> None:
        """Initialize."""
        super().__init__(hass, config_entry, device)
        self.api = api
        self.request_protocols: list[RoborockDyadDataProtocol] = []
        if device.product.category == RoborockCategory.WET_DRY_VAC:
            self.request_protocols = [
                RoborockDyadDataProtocol.STATUS,
                RoborockDyadDataProtocol.POWER,
                RoborockDyadDataProtocol.MESH_LEFT,
                RoborockDyadDataProtocol.BRUSH_LEFT,
                RoborockDyadDataProtocol.ERROR,
                RoborockDyadDataProtocol.TOTAL_RUN_TIME,
            ]
        else:
            _LOGGER.warning("The device you added is not yet supported")

    async def _async_update_data(
        self,
    ) -> dict[RoborockDyadDataProtocol, StateType]:
        return await self.api.query_values(self.request_protocols)
