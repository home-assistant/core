"""Support for esphomelib binary sensors."""
import logging

from typing import TYPE_CHECKING, Optional

from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.components.esphomelib import EsphomelibEntity, \
    platform_async_setup_entry

if TYPE_CHECKING:
    # pylint: disable=unused-import
    from aioesphomeapi.client import BinarySensorInfo, BinarySensorState

DEPENDENCIES = ['esphomelib']
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up esphomelib binary sensors based on a config entry."""
    # pylint: disable=redefined-outer-name
    from aioesphomeapi.client import BinarySensorInfo, BinarySensorState

    await platform_async_setup_entry(
        hass, entry, async_add_entities,
        component_key='binary_sensor',
        info_type=BinarySensorInfo, entity_type=EsphomelibBinarySensor,
        state_type=BinarySensorState
    )


class EsphomelibBinarySensor(EsphomelibEntity, BinarySensorDevice):
    """A binary sensor implementation for esphomelib."""

    @property
    def _static_info(self) -> 'BinarySensorInfo':
        return super()._static_info

    @property
    def _state(self) -> Optional['BinarySensorState']:
        return super()._state

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        if self._static_info.is_status_binary_sensor:
            # Status binary sensors indicated connected state.
            # So in their case what's usually _availability_ is now state
            return self._entry_data.available
        if self._state is None:
            return None
        return self._state.state

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return self._static_info.device_class

    @property
    def available(self):
        """Return True if entity is available."""
        if self._static_info.is_status_binary_sensor:
            return True
        return super(EsphomelibEntity, self).available
