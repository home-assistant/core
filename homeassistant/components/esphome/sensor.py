"""Support for esphome sensors."""
import logging
import math
from typing import Optional

from aioesphomeapi import SensorInfo, SensorState, TextSensorInfo, TextSensorState

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import HomeAssistantType

from . import EsphomeEntity, esphome_state_property, platform_async_setup_entry

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up esphome sensors based on a config entry."""
    await platform_async_setup_entry(
        hass,
        entry,
        async_add_entities,
        component_key="sensor",
        info_type=SensorInfo,
        entity_type=EsphomeSensor,
        state_type=SensorState,
    )
    await platform_async_setup_entry(
        hass,
        entry,
        async_add_entities,
        component_key="text_sensor",
        info_type=TextSensorInfo,
        entity_type=EsphomeTextSensor,
        state_type=TextSensorState,
    )


class EsphomeSensor(EsphomeEntity):
    """A sensor implementation for esphome."""

    @property
    def _static_info(self) -> SensorInfo:
        return super()._static_info

    @property
    def _state(self) -> Optional[SensorState]:
        return super()._state

    @property
    def icon(self) -> str:
        """Return the icon."""
        return self._static_info.icon

    @esphome_state_property
    def state(self) -> Optional[str]:
        """Return the state of the entity."""
        if math.isnan(self._state.state):
            return None
        return "{:.{prec}f}".format(
            self._state.state, prec=self._static_info.accuracy_decimals
        )

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit the value is expressed in."""
        return self._static_info.unit_of_measurement


class EsphomeTextSensor(EsphomeEntity):
    """A text sensor implementation for ESPHome."""

    @property
    def _static_info(self) -> "TextSensorInfo":
        return super()._static_info

    @property
    def _state(self) -> Optional["TextSensorState"]:
        return super()._state

    @property
    def icon(self) -> str:
        """Return the icon."""
        return self._static_info.icon

    @esphome_state_property
    def state(self) -> Optional[str]:
        """Return the state of the entity."""
        return self._state.state
