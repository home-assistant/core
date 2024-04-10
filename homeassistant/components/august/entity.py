"""Base class for August entity."""

from abc import abstractmethod

from yalexs.doorbell import Doorbell, DoorbellDetail
from yalexs.lock import Lock, LockDetail
from yalexs.util import get_configuration_url

from homeassistant.const import ATTR_CONNECTIONS
from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from . import DOMAIN, AugustData
from .const import MANUFACTURER

DEVICE_TYPES = ["keypad", "lock", "camera", "doorbell", "door", "bell"]


class AugustEntityMixin(Entity):
    """Base implementation for August device."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, data: AugustData, device: Doorbell | Lock) -> None:
        """Initialize an August device."""
        super().__init__()
        self._data = data
        self._device = device
        detail = self._detail
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            manufacturer=MANUFACTURER,
            model=detail.model,
            name=device.device_name,
            sw_version=detail.firmware_version,
            suggested_area=_remove_device_types(device.device_name, DEVICE_TYPES),
            configuration_url=get_configuration_url(data.brand),
        )
        if isinstance(detail, LockDetail) and (mac := detail.mac_address):
            self._attr_device_info[ATTR_CONNECTIONS] = {(dr.CONNECTION_BLUETOOTH, mac)}

    @property
    def _device_id(self) -> str:
        return self._device.device_id

    @property
    def _detail(self) -> DoorbellDetail | LockDetail:
        return self._data.get_device_detail(self._device.device_id)

    @property
    def _hyper_bridge(self) -> bool:
        """Check if the lock has a paired hyper bridge."""
        return bool(self._detail.bridge and self._detail.bridge.hyper_bridge)

    @callback
    def _update_from_data_and_write_state(self) -> None:
        self._update_from_data()
        self.async_write_ha_state()

    @abstractmethod
    def _update_from_data(self) -> None:
        """Update the entity state from the data object."""

    async def async_added_to_hass(self) -> None:
        """Subscribe to updates."""
        self.async_on_remove(
            self._data.async_subscribe_device_id(
                self._device_id, self._update_from_data_and_write_state
            )
        )
        self.async_on_remove(
            self._data.activity_stream.async_subscribe_device_id(
                self._device_id, self._update_from_data_and_write_state
            )
        )


def _remove_device_types(name: str, device_types: list[str]) -> str:
    """Strip device types from a string.

    August stores the name as Master Bed Lock
    or Master Bed Door. We can come up with a
    reasonable suggestion by removing the supported
    device types from the string.
    """
    lower_name = name.lower()
    for device_type in device_types:
        lower_name = lower_name.removesuffix(f" {device_type}")
    return name[: len(lower_name)]
