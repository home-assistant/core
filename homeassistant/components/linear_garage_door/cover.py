"""Cover entity for Linear Garage Doors."""

from datetime import timedelta
from typing import Any

from homeassistant.components.cover import (
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import LinearEntity
from .const import DOMAIN
from .coordinator import LinearDevice, LinearUpdateCoordinator

SUPPORTED_SUBDEVICES = ["GDO"]
PARALLEL_UPDATES = 1
SCAN_INTERVAL = timedelta(seconds=10)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Linear Garage Door cover."""
    coordinator: LinearUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        LinearCoverEntity(coordinator, device_id, sub_device_id)
        for device_id, device_data in coordinator.data.items()
        for sub_device_id in device_data.subdevices
        if sub_device_id in SUPPORTED_SUBDEVICES
    )


class LinearCoverEntity(LinearEntity, CoverEntity):
    """Representation of a Linear cover."""

    _attr_supported_features = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE
    _attr_name = None
    _attr_device_class = CoverDeviceClass.GARAGE

    def _get_data(self, data_property: str) -> str:
        """Get a property of the subdevice."""
        return str(
            self.coordinator.data[self._device_id]["subdevices"][self._subdevice].get(
                data_property
            )
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info of a garage door."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=self._device_name,
            manufacturer="Linear",
            model="Garage Door Opener",
        )

    @property
    def linear_device(self) -> LinearDevice:
        """Return the Linear device."""
        return self.coordinator.data[self._device_id]

    @property
    def sub_device(self) -> dict[str, str]:
        """Return the subdevice."""
        return self.linear_device.subdevices[self._sub_device_id]

    @property
    def is_closed(self) -> bool:
        """Return if cover is closed."""
        return self.sub_device.get("Open_B") == "false"

    @property
    def is_opened(self) -> bool:
        """Return if cover is open."""
        return self.sub_device.get("Open_B") == "true"

    @property
    def is_opening(self) -> bool:
        """Return if cover is opening."""
        return self.sub_device.get("Opening_P") == "0"

    @property
    def is_closing(self) -> bool:
        """Return if cover is closing."""
        return self.sub_device.get("Opening_P") == "100"

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the garage door."""
        if self.is_closed:
            return

        await self.coordinator.execute(
            lambda linear: linear.operate_device(
                self._device_id, self._sub_device_id, "Close"
            )
        )

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the garage door."""
        if self.is_opened:
            return

        await self.coordinator.execute(
            lambda linear: linear.operate_device(
                self._device_id, self._sub_device_id, "Open"
            )
        )
