"""The powerview integration base entity."""

from aiopvapi.resources.shade import ATTR_TYPE, BaseShade

from homeassistant.const import ATTR_MODEL, ATTR_SW_VERSION
import homeassistant.helpers.device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_BATTERY_KIND,
    BATTERY_KIND_HARDWIRED,
    DOMAIN,
    FIRMWARE,
    FIRMWARE_BUILD,
    FIRMWARE_REVISION,
    FIRMWARE_SUB_REVISION,
    MANUFACTURER,
)
from .coordinator import PowerviewShadeUpdateCoordinator
from .model import PowerviewDeviceInfo
from .shade_data import PowerviewShadeData, PowerviewShadePositions


class HDEntity(CoordinatorEntity[PowerviewShadeUpdateCoordinator]):
    """Base class for hunter douglas entities."""

    def __init__(
        self,
        coordinator: PowerviewShadeUpdateCoordinator,
        device_info: PowerviewDeviceInfo,
        room_name: str,
        unique_id: str,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._room_name = room_name
        self._attr_unique_id = unique_id
        self._device_info = device_info

    @property
    def data(self) -> PowerviewShadeData:
        """Return the PowerviewShadeData."""
        return self.coordinator.data

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device_info of the device."""
        firmware = self._device_info.firmware
        sw_version = f"{firmware[FIRMWARE_REVISION]}.{firmware[FIRMWARE_SUB_REVISION]}.{firmware[FIRMWARE_BUILD]}"
        return DeviceInfo(
            connections={(dr.CONNECTION_NETWORK_MAC, self._device_info.mac_address)},
            identifiers={(DOMAIN, self._device_info.serial_number)},
            manufacturer=MANUFACTURER,
            model=self._device_info.model,
            name=self._device_info.name,
            suggested_area=self._room_name,
            sw_version=sw_version,
            configuration_url=f"http://{self._device_info.hub_address}/api/shades",
        )


class ShadeEntity(HDEntity):
    """Base class for hunter douglas shade entities."""

    def __init__(
        self,
        coordinator: PowerviewShadeUpdateCoordinator,
        device_info: PowerviewDeviceInfo,
        room_name: str,
        shade: BaseShade,
        shade_name: str,
    ) -> None:
        """Initialize the shade."""
        super().__init__(coordinator, device_info, room_name, shade.id)
        self._shade_name = shade_name
        self._shade = shade
        self._is_hard_wired = bool(
            shade.raw_data.get(ATTR_BATTERY_KIND) == BATTERY_KIND_HARDWIRED
        )

    @property
    def positions(self) -> PowerviewShadePositions:
        """Return the PowerviewShadeData."""
        return self.data.get_shade_positions(self._shade.id)

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device_info of the device."""

        device_info = DeviceInfo(
            identifiers={(DOMAIN, self._shade.id)},
            name=self._shade_name,
            suggested_area=self._room_name,
            manufacturer=MANUFACTURER,
            model=str(self._shade.raw_data[ATTR_TYPE]),
            via_device=(DOMAIN, self._device_info.serial_number),
            configuration_url=(
                f"http://{self._device_info.hub_address}/api/shades/{self._shade.id}"
            ),
        )

        for shade in self._shade.shade_types:
            if str(shade.shade_type) == device_info[ATTR_MODEL]:
                device_info[ATTR_MODEL] = shade.description
                break

        if FIRMWARE not in self._shade.raw_data:
            return device_info

        firmware = self._shade.raw_data[FIRMWARE]
        sw_version = f"{firmware[FIRMWARE_REVISION]}.{firmware[FIRMWARE_SUB_REVISION]}.{firmware[FIRMWARE_BUILD]}"

        device_info[ATTR_SW_VERSION] = sw_version

        return device_info
