"""Support for esphomelib sensors."""
import logging
import math
from typing import Optional

from homeassistant.components.esphomelib import EsphomelibEntity, \
    platform_async_setup_entry

DEPENDENCIES = ['esphomelib']
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up esphomelib sensors based on a config entry."""
    from aioesphomeapi.client import SensorInfo, SensorState, TextSensorInfo, \
        TextSensorState

    await platform_async_setup_entry(
        hass, entry, async_add_entities,
        component_key='sensor',
        info_type=SensorInfo, entity_type=EsphomelibSensor,
        state_type=SensorState
    )
    await platform_async_setup_entry(
        hass, entry, async_add_entities,
        component_key='text_sensor',
        info_type=TextSensorInfo, entity_type=EsphomelibTextSensor,
        state_type=TextSensorState
    )


class EsphomelibSensor(EsphomelibEntity):
    """A sensor implementation for esphomelib."""

    @property
    def icon(self) -> str:
        """Return the icon."""
        return self.info.icon

    @property
    def state(self) -> Optional[str]:
        """Return the state of the entity."""
        if self._state is None:
            return None
        if math.isnan(self._state.state):
            return None
        return '{:.{prec}f}'.format(
            self._state.state, prec=self.info.accuracy_decimals)

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self.info.unit_of_measurement


class EsphomelibTextSensor(EsphomelibEntity):
    """A text sensor implementation for esphomelib."""

    @property
    def icon(self) -> str:
        """Return the icon."""
        return self.info.icon

    @property
    def state(self) -> Optional[str]:
        """Return the state of the entity."""
        if self._state is None:
            return None
        return self._state.state
