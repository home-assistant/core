"""Base class for August entity."""
from abc import abstractmethod

from yalexs.doorbell import Doorbell
from yalexs.lock import Lock
from yalexs.util import get_configuration_url

from homeassistant.core import callback
from homeassistant.helpers.entity import DeviceInfo, Entity

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
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            manufacturer=MANUFACTURER,
            model=self._detail.model,
            name=device.device_name,
            sw_version=self._detail.firmware_version,
            suggested_area=_remove_device_types(device.device_name, DEVICE_TYPES),
            configuration_url=get_configuration_url(data.brand),
        )

    @property
    def _device_id(self):
        return self._device.device_id

    @property
    def _detail(self):
        return self._data.get_device_detail(self._device.device_id)

    @property
    def _hyper_bridge(self):
        """Check if the lock has a paired hyper bridge."""
        return bool(self._detail.bridge and self._detail.bridge.hyper_bridge)

    @callback
    def _update_from_data_and_write_state(self):
        self._update_from_data()
        self.async_write_ha_state()

    @abstractmethod
    def _update_from_data(self):
        """Update the entity state from the data object."""

    async def async_added_to_hass(self):
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


def _remove_device_types(name, device_types):
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
