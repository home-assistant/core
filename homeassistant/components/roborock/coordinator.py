"""Roborock Coordinator."""

from __future__ import annotations

from datetime import timedelta
import logging

from propcache import cached_property
from roborock import HomeDataRoom
from roborock.code_mappings import RoborockCategory
from roborock.containers import DeviceData, HomeDataDevice, HomeDataProduct, NetworkInfo
from roborock.exceptions import RoborockException
from roborock.roborock_message import RoborockDyadDataProtocol, RoborockZeoProtocol
from roborock.roborock_typing import DeviceProp
from roborock.version_1_apis.roborock_local_client_v1 import RoborockLocalClientV1
from roborock.version_1_apis.roborock_mqtt_client_v1 import RoborockMqttClientV1
from roborock.version_a01_apis import RoborockClientA01

from homeassistant.const import ATTR_CONNECTIONS
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import slugify

from .const import DOMAIN
from .models import RoborockA01HassDeviceInfo, RoborockHassDeviceInfo, RoborockMapInfo

SCAN_INTERVAL = timedelta(seconds=30)

_LOGGER = logging.getLogger(__name__)


class RoborockDataUpdateCoordinator(DataUpdateCoordinator[DeviceProp]):
    """Class to manage fetching data from the API."""

    def __init__(
        self,
        hass: HomeAssistant,
        device: HomeDataDevice,
        device_networking: NetworkInfo,
        product_info: HomeDataProduct,
        cloud_api: RoborockMqttClientV1,
        home_data_rooms: list[HomeDataRoom],
    ) -> None:
        """Initialize."""
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=SCAN_INTERVAL)
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
            identifiers={(DOMAIN, self.roborock_device_info.device.duid)},
            manufacturer="Roborock",
            model=self.roborock_device_info.product.model,
            model_id=self.roborock_device_info.product.model,
            sw_version=self.roborock_device_info.device.fv,
        )
        self.current_map: int | None = None

        if mac := self.roborock_device_info.network_info.mac:
            self.device_info[ATTR_CONNECTIONS] = {(dr.CONNECTION_NETWORK_MAC, mac)}
        # Maps from map flag to map name
        self.maps: dict[int, RoborockMapInfo] = {}
        self._home_data_rooms = {str(room.id): room.name for room in home_data_rooms}

    async def verify_api(self) -> None:
        """Verify that the api is reachable. If it is not, switch clients."""
        if isinstance(self.api, RoborockLocalClientV1):
            try:
                await self.api.ping()
            except RoborockException:
                _LOGGER.warning(
                    "Using the cloud API for device %s. This is not recommended as it can lead to rate limiting. We recommend making your vacuum accessible by your Home Assistant instance",
                    self.roborock_device_info.device.duid,
                )
                await self.api.async_disconnect()
                # We use the cloud api if the local api fails to connect.
                self.api = self.cloud_api
                # Right now this should never be called if the cloud api is the primary api,
                # but in the future if it is, a new else should be added.

    async def release(self) -> None:
        """Disconnect from API."""
        await self.api.async_release()
        await self.cloud_api.async_release()

    async def _update_device_prop(self) -> None:
        """Update device properties."""
        device_prop = await self.api.get_prop()
        if device_prop:
            if self.roborock_device_info.props:
                self.roborock_device_info.props.update(device_prop)
            else:
                self.roborock_device_info.props = device_prop

    async def _async_update_data(self) -> DeviceProp:
        """Update data via library."""
        try:
            # Update device props and standard api information
            await self._update_device_prop()
            # Set the new map id from the updated device props
            self._set_current_map()
            # Get the rooms for that map id.
            await self.get_rooms()
        except RoborockException as ex:
            raise UpdateFailed(ex) from ex
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

    async def get_maps(self) -> None:
        """Add a map to the coordinators mapping."""
        maps = await self.api.get_multi_maps_list()
        if maps and maps.map_info:
            for roborock_map in maps.map_info:
                self.maps[roborock_map.mapFlag] = RoborockMapInfo(
                    flag=roborock_map.mapFlag, name=roborock_map.name, rooms={}
                )

    async def get_rooms(self) -> None:
        """Get all of the rooms for the current map."""
        # The api is only able to access rooms for the currently selected map
        # So it is important this is only called when you have the map you care
        # about selected.
        if self.current_map in self.maps:
            iot_rooms = await self.api.get_room_mapping()
            if iot_rooms is not None:
                for room in iot_rooms:
                    self.maps[self.current_map].rooms[room.segment_id] = (
                        self._home_data_rooms.get(room.iot_id, "Unknown")
                    )

    @cached_property
    def duid(self) -> str:
        """Get the unique id of the device as specified by Roborock."""
        return self.roborock_device_info.device.duid

    @cached_property
    def duid_slug(self) -> str:
        """Get the slug of the duid."""
        return slugify(self.duid)


class RoborockDataUpdateCoordinatorA01(
    DataUpdateCoordinator[
        dict[RoborockDyadDataProtocol | RoborockZeoProtocol, StateType]
    ]
):
    """Class to manage fetching data from the API for A01 devices."""

    def __init__(
        self,
        hass: HomeAssistant,
        device: HomeDataDevice,
        product_info: HomeDataProduct,
        api: RoborockClientA01,
    ) -> None:
        """Initialize."""
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=SCAN_INTERVAL)
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

    async def release(self) -> None:
        """Disconnect from API."""
        await self.api.async_release()

    @cached_property
    def duid(self) -> str:
        """Get the unique id of the device as specified by Roborock."""
        return self.roborock_device_info.device.duid

    @cached_property
    def duid_slug(self) -> str:
        """Get the slug of the duid."""
        return slugify(self.duid)
