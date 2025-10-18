"""Roborock Coordinator."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Any, TypeVar

from propcache.api import cached_property
from roborock.data import HomeDataScene, RoborockCategory, UserData
from roborock.devices.device import RoborockDevice
from roborock.devices.traits.a01 import DyadApi, ZeoApi
from roborock.devices.traits.v1 import PropertiesApi
from roborock.exceptions import RoborockDeviceBusy, RoborockException
from roborock.roborock_message import RoborockDyadDataProtocol, RoborockZeoProtocol
from roborock.web_api import RoborockApiClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_CONNECTIONS
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.issue_registry import (
    IssueSeverity,
    async_create_issue,
    async_delete_issue,
)
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
from .models import DeviceState, RoborockMapInfo
from .roborock_storage import RoborockMapStorage

SCAN_INTERVAL = timedelta(seconds=30)

_LOGGER = logging.getLogger(__name__)


@dataclass
class RoborockCoordinators:
    """Roborock coordinators type."""

    api_client: UserApiClient
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
        _LOGGER.debug(
            "Creating coordinator for device %s - %s", device.duid, device.name
        )
        self.device_info = DeviceInfo(
            name=self._device.device_info.name,
            identifiers={(DOMAIN, self.duid)},
            manufacturer="Roborock",
            model=self._device.product.model,
            model_id=self._device.product.model,
            sw_version=self._device.device_info.fv,
        )
        self.current_map: int | None = None
        if mac := properties_api.network_info.mac:
            self.device_info[ATTR_CONNECTIONS] = {
                (dr.CONNECTION_NETWORK_MAC, dr.format_mac(mac))
            }
        # Maps from map flag to map name
        self.maps: dict[int, RoborockMapInfo] = {}
        self.map_storage = RoborockMapStorage(
            hass, self.config_entry.entry_id, self.duid_slug
        )
        self.last_update_state: str | None = None

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
        # This will either read from the cache or load information about the
        # home and cache the detail. The device can only load information for
        # the current map so from here forward.
        await self.properties_api.status.refresh()
        try:
            await self.properties_api.home.discover_home()
        except RoborockDeviceBusy:
            _LOGGER.info("Home discovery skipped while device is busy/cleaning")

        roborock_maps = list((self.properties_api.home.home_cache or {}).values())
        # Handle loading any stored images for the current or formerly active
        # maps here. A single active map for each device is refreshed regularly,
        # and the others maps are served from the cache.
        stored_images = await asyncio.gather(
            *[
                self.map_storage.async_load_map(roborock_map.map_flag)
                for roborock_map in roborock_maps
            ]
        )
        self.maps = {
            roborock_map.map_flag: RoborockMapInfo(
                flag=roborock_map.map_flag,
                name=roborock_map.name or f"Map {roborock_map.map_flag}",
                image=image,
                last_updated=dt_util.utcnow() - IMAGE_CACHE_INTERVAL,
                map_data=None,
            )
            for image, roborock_map in zip(stored_images, roborock_maps, strict=False)
        }

    async def update_map(self) -> None:
        """Update the currently selected map."""
        # The current map was set in the props update, so these can be done without
        # worry of applying them to the wrong map.
        if self.current_map is None or self.current_map not in self.maps:
            # This exists as a safeguard/ to keep mypy happy.
            return
        try:
            await self.properties_api.map_content.refresh()
        except RoborockException as ex:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="map_failure",
            ) from ex
        current_roborock_map_info = self.maps[self.current_map]
        parsed_image = self.properties_api.map_content.image_content
        parsed_map = self.properties_api.map_content.map_data
        if parsed_image is not None and parsed_image != current_roborock_map_info.image:
            await self.map_storage.async_save_map(
                self.current_map,
                parsed_image,
            )
            current_roborock_map_info.image = parsed_image
            current_roborock_map_info.last_updated = dt_util.utcnow()
        current_roborock_map_info.map_data = parsed_map

    async def async_shutdown(self) -> None:
        """Shutdown the coordinator."""
        await super().async_shutdown()
        await self.map_storage.flush()

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

        # Set the new map id from the updated device props
        self._set_current_map()
        # Get the rooms for that map id.

        # If the vacuum is currently cleaning and it has been IMAGE_CACHE_INTERVAL
        # since the last map update, you can update the map.
        new_status = self.properties_api.status
        if (
            self.current_map is not None
            and (current_map := self.maps.get(self.current_map))
            and (
                (
                    new_status.in_cleaning
                    and (dt_util.utcnow() - current_map.last_updated)
                    > IMAGE_CACHE_INTERVAL
                )
                or self.last_update_state != new_status.state_name
            )
        ):
            _LOGGER.debug("Updating map for map id %s", self.current_map)
            try:
                await self.update_map()
            except HomeAssistantError as err:
                _LOGGER.debug("Failed to update map: %s", err)

        try:
            await self.properties_api.home.discover_home()
            await self.properties_api.home.refresh()
        except RoborockDeviceBusy as ex:
            _LOGGER.debug("Not refreshing home while device is busy: %s", ex)
        except RoborockException as ex:
            _LOGGER.debug("Failed to update data: %s", ex)
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_data_fail",
            ) from ex

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

    def _set_current_map(self) -> None:
        if (
            self.properties_api.status is not None
            and self.properties_api.status.current_map is not None
        ):
            self.current_map = self.properties_api.status.current_map

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


class UserApiClient:
    """Wrapper around the Roborock API client."""

    def __init__(
        self,
        api_client: RoborockApiClient,
        user_data: UserData,
    ) -> None:
        """Initialize."""
        self._api_client = api_client
        self._user_data = user_data

    async def get_routines(self, duid: str) -> list[HomeDataScene]:
        """Get routines."""
        try:
            return await self._api_client.get_scenes(self._user_data, duid)
        except RoborockException as err:
            _LOGGER.error("Failed to get routines %s", err)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
                translation_placeholders={
                    "command": "get_scenes",
                },
            ) from err

    async def execute_routines(self, routine_id: int) -> None:
        """Execute routines."""
        try:
            await self._api_client.execute_scene(self._user_data, routine_id)
        except RoborockException as err:
            _LOGGER.error("Failed to execute routines %s %s", routine_id, err)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
                translation_placeholders={
                    "command": "execute_scene",
                },
            ) from err


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
