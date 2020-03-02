"""Base class for August entity."""

import logging

from homeassistant.core import callback
from homeassistant.helpers.entity import Entity

from . import DEFAULT_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)


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
        return {
            "identifiers": {(DOMAIN, self._device_id)},
            "name": self._device.device_name,
            "manufacturer": DEFAULT_NAME,
            "sw_version": self._detail.firmware_version,
            "model": self._detail.model,
        }

    @callback
    def _update_from_data_and_write_state(self):
        self._update_from_data()
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """Subscribe to updates."""
        self._data.async_subscribe_device_id(
            self._device_id, self._update_from_data_and_write_state
        )
        self._data.activity_stream.async_subscribe_device_id(
            self._device_id, self._update_from_data_and_write_state
        )

    async def async_will_remove_from_hass(self):
        """Undo subscription."""
        self._data.async_unsubscribe_device_id(
            self._device_id, self._update_from_data_and_write_state
        )
        self._data.activity_stream.async_unsubscribe_device_id(
            self._device_id, self._update_from_data_and_write_state
        )
