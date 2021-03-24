"""Support for esphome sensors."""
from __future__ import annotations

import math

from aioesphomeapi import SensorInfo, SensorState, TextSensorInfo, TextSensorState
import voluptuous as vol

from homeassistant.components.sensor import DEVICE_CLASSES, SensorEntity
from homeassistant.config_entries import ConfigEntry
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import HomeAssistantType

from . import EsphomeEntity, esphome_state_property, platform_async_setup_entry


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


# https://github.com/PyCQA/pylint/issues/3150 for all @esphome_state_property
# pylint: disable=invalid-overridden-method


class EsphomeSensor(EsphomeEntity, SensorEntity):
    """A sensor implementation for esphome."""

    @property
    def _static_info(self) -> SensorInfo:
        return super()._static_info

    @property
    def _state(self) -> SensorState | None:
        return super()._state

    @property
    def icon(self) -> str:
        """Return the icon."""
        if not self._static_info.icon or self._static_info.device_class:
            return None
        return vol.Schema(cv.icon)(self._static_info.icon)

    @property
    def force_update(self) -> bool:
        """Return if this sensor should force a state update."""
        return self._static_info.force_update

    @esphome_state_property
    def state(self) -> str | None:
        """Return the state of the entity."""
        if math.isnan(self._state.state):
            return None
        if self._state.missing_state:
            return None
        return f"{self._state.state:.{self._static_info.accuracy_decimals}f}"

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit the value is expressed in."""
        if not self._static_info.unit_of_measurement:
            return None
        return self._static_info.unit_of_measurement

    @property
    def device_class(self) -> str:
        """Return the class of this device, from component DEVICE_CLASSES."""
        if self._static_info.device_class not in DEVICE_CLASSES:
            return None
        return self._static_info.device_class


class EsphomeTextSensor(EsphomeEntity, SensorEntity):
    """A text sensor implementation for ESPHome."""

    @property
    def _static_info(self) -> TextSensorInfo:
        return super()._static_info

    @property
    def _state(self) -> TextSensorState | None:
        return super()._state

    @property
    def icon(self) -> str:
        """Return the icon."""
        return self._static_info.icon

    @esphome_state_property
    def state(self) -> str | None:
        """Return the state of the entity."""
        if self._state.missing_state:
            return None
        return self._state.state
