"""Base class for August entity."""
from homeassistant.core import callback
from homeassistant.helpers.entity import Entity

from . import DOMAIN
from .const import MANUFACTURER

DEVICE_TYPES = ["keypad", "lock", "camera", "doorbell", "door", "bell"]


class AugustEntityMixin(Entity):
    """Base implementation for August device."""

    def __init__(self, data, device):
        """Initialize an August device."""
        super().__init__()
        self._data = data
        self._device = device

    @property
    def should_poll(self):
        """Return False, updates are controlled via the hub."""
        return False

    @property
    def _device_id(self):
        return self._device.device_id

    @property
    def _detail(self):
        return self._data.get_device_detail(self._device.device_id)

    @property
    def device_info(self):
        """Return the device_info of the device."""
        name = self._device.device_name
        return {
            "identifiers": {(DOMAIN, self._device_id)},
            "name": name,
            "manufacturer": MANUFACTURER,
            "sw_version": self._detail.firmware_version,
            "model": self._detail.model,
            "suggested_area": _remove_device_types(name, DEVICE_TYPES),
        }

    @callback
    def _update_from_data_and_write_state(self):
        self._update_from_data()
        self.async_write_ha_state()

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
        device_type_with_space = f" {device_type}"
        if lower_name.endswith(device_type_with_space):
            lower_name = lower_name[: -len(device_type_with_space)]
    return name[: len(lower_name)]
