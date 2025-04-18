"""Roborock Coordinator."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import timedelta
import io
import logging

from propcache.api import cached_property
from roborock import HomeDataRoom
from roborock.code_mappings import RoborockCategory
from roborock.containers import (
    DeviceData,
    HomeDataDevice,
    HomeDataProduct,
    HomeDataScene,
    NetworkInfo,
    UserData,
)
from roborock.exceptions import RoborockException
from roborock.roborock_message import RoborockDyadDataProtocol, RoborockZeoProtocol
from roborock.roborock_typing import DeviceProp
from roborock.version_1_apis.roborock_local_client_v1 import RoborockLocalClientV1
from roborock.version_1_apis.roborock_mqtt_client_v1 import RoborockMqttClientV1
from roborock.version_a01_apis import RoborockClientA01
from roborock.web_api import RoborockApiClient
from vacuum_map_parser_base.config.color import ColorsPalette
from vacuum_map_parser_base.config.image_config import ImageConfig
from vacuum_map_parser_base.config.size import Sizes
from vacuum_map_parser_base.map_data import MapData
from vacuum_map_parser_roborock.map_data_parser import RoborockMapDataParser

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
    DEFAULT_DRAWABLES,
    DOMAIN,
    DRAWABLES,
    IMAGE_CACHE_INTERVAL,
    MAP_FILE_FORMAT,
    MAP_SCALE,
    MAP_SLEEP,
    V1_CLOUD_IN_CLEANING_INTERVAL,
    V1_CLOUD_NOT_CLEANING_INTERVAL,
    V1_LOCAL_IN_CLEANING_INTERVAL,
    V1_LOCAL_NOT_CLEANING_INTERVAL,
)
from .models import RoborockA01HassDeviceInfo, RoborockHassDeviceInfo, RoborockMapInfo
from .roborock_storage import RoborockMapStorage

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


class RoborockDataUpdateCoordinator(DataUpdateCoordinator[DeviceProp]):
    """Class to manage fetching data from the API."""

    config_entry: RoborockConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: RoborockConfigEntry,
        device: HomeDataDevice,
        device_networking: NetworkInfo,
        product_info: HomeDataProduct,
        cloud_api: RoborockMqttClientV1,
        home_data_rooms: list[HomeDataRoom],
        api_client: RoborockApiClient,
        user_data: UserData,
    ) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            # Assume we can use the local api.
            update_interval=V1_LOCAL_NOT_CLEANING_INTERVAL,
        )
        self.roborock_device_info = RoborockHassDeviceInfo(
            device,
            device_networking,
            product_info,
            DeviceProp(),
        )
        device_data = DeviceData(device, product_info.model, device_networking.ip)
        self.api: RoborockLocalClientV1 | RoborockMqttClientV1 = RoborockLocalClientV1(
            device_data, queue_timeout=5
        )
        self.cloud_api = cloud_api
        self.device_info = DeviceInfo(
            name=self.roborock_device_info.device.name,
            identifiers={(DOMAIN, self.duid)},
            manufacturer="Roborock",
            model=self.roborock_device_info.product.model,
            model_id=self.roborock_device_info.product.model,
            sw_version=self.roborock_device_info.device.fv,
        )
        self.current_map: int | None = None

        if mac := self.roborock_device_info.network_info.mac:
            self.device_info[ATTR_CONNECTIONS] = {
                (dr.CONNECTION_NETWORK_MAC, dr.format_mac(mac))
            }
        # Maps from map flag to map name
        self.maps: dict[int, RoborockMapInfo] = {}
        self._home_data_rooms = {str(room.id): room.name for room in home_data_rooms}
        self.map_storage = RoborockMapStorage(
            hass, self.config_entry.entry_id, self.duid_slug
        )
        self._user_data = user_data
        self._api_client = api_client
        self._is_cloud_api = False
        drawables = [
            drawable
            for drawable, default_value in DEFAULT_DRAWABLES.items()
            if config_entry.options.get(DRAWABLES, {}).get(drawable, default_value)
        ]
        self.map_parser = RoborockMapDataParser(
            ColorsPalette(),
            Sizes({k: v * MAP_SCALE for k, v in Sizes.SIZES.items()}),
            drawables,
            ImageConfig(scale=MAP_SCALE),
            [],
        )
        self.last_update_state: str | None = None

    @cached_property
    def dock_device_info(self) -> DeviceInfo:
        """Gets the device info for the dock.

        This must happen after the coordinator does the first update.
        Which will be the case when this is called.
        """
        dock_type = self.roborock_device_info.props.status.dock_type
        return DeviceInfo(
            name=f"{self.roborock_device_info.device.name} Dock",
            identifiers={(DOMAIN, f"{self.duid}_dock")},
            manufacturer="Roborock",
            model=f"{self.roborock_device_info.product.model} Dock",
            model_id=str(dock_type.value) if dock_type is not None else "Unknown",
            sw_version=self.roborock_device_info.device.fv,
        )

    def parse_map_data_v1(
        self, map_bytes: bytes
    ) -> tuple[bytes | None, MapData | None]:
        """Parse map_bytes and return MapData and the image."""
        try:
            parsed_map = self.map_parser.parse(map_bytes)
        except (IndexError, ValueError) as err:
            _LOGGER.debug("Exception when parsing map contents: %s", err)
            return None, None
        if parsed_map.image is None:
            return None, None
        img_byte_arr = io.BytesIO()
        parsed_map.image.data.save(img_byte_arr, format=MAP_FILE_FORMAT)
        return img_byte_arr.getvalue(), parsed_map

    async def _async_setup(self) -> None:
        """Set up the coordinator."""
        # Verify we can communicate locally - if we can't, switch to cloud api
        await self._verify_api()
        self.api.is_available = True

        try:
            maps = await self.api.get_multi_maps_list()
        except RoborockException as err:
            _LOGGER.debug("Failed to get maps: %s", err)
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="map_failure",
                translation_placeholders={"error": str(err)},
            ) from err
        # Rooms names populated later with calls to `set_current_map_rooms` for each map
        roborock_maps = maps.map_info if (maps and maps.map_info) else ()
        stored_images = await asyncio.gather(
            *[
                self.map_storage.async_load_map(roborock_map.mapFlag)
                for roborock_map in roborock_maps
            ]
        )
        self.maps = {
            roborock_map.mapFlag: RoborockMapInfo(
                flag=roborock_map.mapFlag,
                name=roborock_map.name or f"Map {roborock_map.mapFlag}",
                rooms={},
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
            response = await self.cloud_api.get_map_v1()
        except RoborockException as ex:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="map_failure",
            ) from ex
        if not isinstance(response, bytes):
            _LOGGER.debug("Failed to parse map contents: %s", response)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="map_failure",
            )
        parsed_image, parsed_map = self.parse_map_data_v1(response)
        if parsed_image is None or parsed_map is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="map_failure",
            )
        current_roborock_map_info = self.maps[self.current_map]
        if parsed_image != self.maps[self.current_map].image:
            await self.map_storage.async_save_map(
                self.current_map,
                parsed_image,
            )
            current_roborock_map_info.image = parsed_image
            current_roborock_map_info.last_updated = dt_util.utcnow()
        current_roborock_map_info.map_data = parsed_map

    async def _verify_api(self) -> None:
        """Verify that the api is reachable. If it is not, switch clients."""
        if isinstance(self.api, RoborockLocalClientV1):
            try:
                await self.api.ping()
            except RoborockException:
                _LOGGER.warning(
                    "Using the cloud API for device %s. This is not recommended as it can lead to rate limiting. We recommend making your vacuum accessible by your Home Assistant instance",
                    self.duid,
                )
                await self.api.async_disconnect()
                # We use the cloud api if the local api fails to connect.
                self.api = self.cloud_api
                self.update_interval = V1_CLOUD_NOT_CLEANING_INTERVAL
                self._is_cloud_api = True
                # Right now this should never be called if the cloud api is the primary api,
                # but in the future if it is, a new else should be added.

    async def async_shutdown(self) -> None:
        """Shutdown the coordinator."""
        await super().async_shutdown()
        await asyncio.gather(
            self.map_storage.flush(),
            self.api.async_release(),
            self.cloud_api.async_release(),
        )

    async def _update_device_prop(self) -> None:
        """Update device properties."""
        if (device_prop := await self.api.get_prop()) is not None:
            self.roborock_device_info.props.update(device_prop)

    async def _async_update_data(self) -> DeviceProp:
        """Update data via library."""
        try:
            # Update device props and standard api information
            await self._update_device_prop()
            # Set the new map id from the updated device props
            self._set_current_map()
            # Get the rooms for that map id.

            # If the vacuum is currently cleaning and it has been IMAGE_CACHE_INTERVAL
            # since the last map update, you can update the map.
            new_status = self.roborock_device_info.props.status
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
                try:
                    await self.update_map()
                except HomeAssistantError as err:
                    _LOGGER.debug("Failed to update map: %s", err)
            await self.set_current_map_rooms()
        except RoborockException as ex:
            _LOGGER.debug("Failed to update data: %s", ex)
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_data_fail",
            ) from ex
        if self.roborock_device_info.props.status.in_cleaning:
            if self._is_cloud_api:
                self.update_interval = V1_CLOUD_IN_CLEANING_INTERVAL
            else:
                self.update_interval = V1_LOCAL_IN_CLEANING_INTERVAL
        elif self._is_cloud_api:
            self.update_interval = V1_CLOUD_NOT_CLEANING_INTERVAL
        else:
            self.update_interval = V1_LOCAL_NOT_CLEANING_INTERVAL
        self.last_update_state = self.roborock_device_info.props.status.state_name
        return self.roborock_device_info.props

    def _set_current_map(self) -> None:
        if (
            self.roborock_device_info.props.status is not None
            and self.roborock_device_info.props.status.map_status is not None
        ):
            # The map status represents the map flag as flag * 4 + 3 -
            # so we have to invert that in order to get the map flag that we can use to set the current map.
            self.current_map = (
                self.roborock_device_info.props.status.map_status - 3
            ) // 4

    async def set_current_map_rooms(self) -> None:
        """Fetch all of the rooms for the current map and set on RoborockMapInfo."""
        # The api is only able to access rooms for the currently selected map
        # So it is important this is only called when you have the map you care
        # about selected.
        if self.current_map is None or self.current_map not in self.maps:
            return
        room_mapping = await self.api.get_room_mapping()
        self.maps[self.current_map].rooms = {
            room.segment_id: self._home_data_rooms.get(room.iot_id, "Unknown")
            for room in room_mapping or ()
        }

    async def get_routines(self) -> list[HomeDataScene]:
        """Get routines."""
        try:
            return await self._api_client.get_scenes(self._user_data, self.duid)
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

    @cached_property
    def duid(self) -> str:
        """Get the unique id of the device as specified by Roborock."""
        return self.roborock_device_info.device.duid

    @cached_property
    def duid_slug(self) -> str:
        """Get the slug of the duid."""
        return slugify(self.duid)

    async def refresh_coordinator_map(self) -> None:
        """Get the starting map information for all maps for this device.

        The following steps must be done synchronously.
        Only one map can be loaded at a time per device.
        """
        cur_map = self.current_map
        # This won't be None at this point as the coordinator will have run first.
        if cur_map is None:
            # If we don't have a cur map(shouldn't happen) just
            # return as we can't do anything.
            return
        map_flags = sorted(self.maps, key=lambda data: data == cur_map, reverse=True)
        for map_flag in map_flags:
            if map_flag != cur_map:
                # Only change the map and sleep if we have multiple maps.
                await self.api.load_multi_map(map_flag)
                self.current_map = map_flag
                # We cannot get the map until the roborock servers fully process the
                # map change.
                await asyncio.sleep(MAP_SLEEP)
            tasks = [self.set_current_map_rooms()]
            # The image is set within async_setup, so if it exists, we have it here.
            if self.maps[map_flag].image is None:
                # If we don't have a cached map, let's update it here so that it can be
                # cached in the future.
                tasks.append(self.update_map())
            # If either of these fail, we don't care, and we want to continue.
            await asyncio.gather(*tasks, return_exceptions=True)

        if len(self.maps) != 1:
            # Set the map back to the map the user previously had selected so that it
            # does not change the end user's app.
            # Only needs to happen when we changed maps above.
            await self.api.load_multi_map(cur_map)
            self.current_map = cur_map


class RoborockDataUpdateCoordinatorA01(
    DataUpdateCoordinator[
        dict[RoborockDyadDataProtocol | RoborockZeoProtocol, StateType]
    ]
):
    """Class to manage fetching data from the API for A01 devices."""

    config_entry: RoborockConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: RoborockConfigEntry,
        device: HomeDataDevice,
        product_info: HomeDataProduct,
        api: RoborockClientA01,
    ) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=A01_UPDATE_INTERVAL,
        )
        self.api = api
        self.device_info = DeviceInfo(
            name=device.name,
            identifiers={(DOMAIN, device.duid)},
            manufacturer="Roborock",
            model=product_info.model,
            sw_version=device.fv,
        )
        self.request_protocols: list[
            RoborockDyadDataProtocol | RoborockZeoProtocol
        ] = []
        if product_info.category == RoborockCategory.WET_DRY_VAC:
            self.request_protocols = [
                RoborockDyadDataProtocol.STATUS,
                RoborockDyadDataProtocol.POWER,
                RoborockDyadDataProtocol.MESH_LEFT,
                RoborockDyadDataProtocol.BRUSH_LEFT,
                RoborockDyadDataProtocol.ERROR,
                RoborockDyadDataProtocol.TOTAL_RUN_TIME,
            ]
        elif product_info.category == RoborockCategory.WASHING_MACHINE:
            self.request_protocols = [
                RoborockZeoProtocol.STATE,
                RoborockZeoProtocol.COUNTDOWN,
                RoborockZeoProtocol.WASHING_LEFT,
                RoborockZeoProtocol.ERROR,
            ]
        else:
            _LOGGER.warning("The device you added is not yet supported")
        self.roborock_device_info = RoborockA01HassDeviceInfo(device, product_info)

    async def _async_update_data(
        self,
    ) -> dict[RoborockDyadDataProtocol | RoborockZeoProtocol, StateType]:
        return await self.api.update_values(self.request_protocols)

    async def async_shutdown(self) -> None:
        """Shutdown the coordinator on config entry unload."""
        await super().async_shutdown()
        await self.api.async_release()

    @cached_property
    def duid(self) -> str:
        """Get the unique id of the device as specified by Roborock."""
        return self.roborock_device_info.device.duid

    @cached_property
    def duid_slug(self) -> str:
        """Get the slug of the duid."""
        return slugify(self.duid)
