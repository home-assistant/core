"""Support for esphome sensors."""
from __future__ import annotations

from datetime import datetime
import math

from aioesphomeapi import (
    SensorInfo,
    SensorState,
    SensorStateClass as EsphomeSensorStateClass,
    TextSensorInfo,
    TextSensorState,
)
from aioesphomeapi.model import LastResetType

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt
from homeassistant.util.enum import try_parse_enum

from . import (
    EsphomeEntity,
    EsphomeEnumMapper,
    esphome_state_property,
    platform_async_setup_entry,
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
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


_STATE_CLASSES: EsphomeEnumMapper[
    EsphomeSensorStateClass, SensorStateClass | None
] = EsphomeEnumMapper(
    {
        EsphomeSensorStateClass.NONE: None,
        EsphomeSensorStateClass.MEASUREMENT: SensorStateClass.MEASUREMENT,
        EsphomeSensorStateClass.TOTAL_INCREASING: SensorStateClass.TOTAL_INCREASING,
        EsphomeSensorStateClass.TOTAL: SensorStateClass.TOTAL,
    }
)


class EsphomeSensor(EsphomeEntity[SensorInfo, SensorState], SensorEntity):
    """A sensor implementation for esphome."""

    @property
    def force_update(self) -> bool:
        """Return if this sensor should force a state update."""
        return self._static_info.force_update

    @property
    @esphome_state_property
    def native_value(self) -> datetime | str | None:
        """Return the state of the entity."""
        if math.isnan(self._state.state):
            return None
        if self._state.missing_state:
            return None
        if self.device_class == SensorDeviceClass.TIMESTAMP:
            return dt.utc_from_timestamp(self._state.state)
        return f"{self._state.state:.{self._static_info.accuracy_decimals}f}"

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit the value is expressed in."""
        if not self._static_info.unit_of_measurement:
            return None
        return self._static_info.unit_of_measurement

    @property
    def device_class(self) -> SensorDeviceClass | None:
        """Return the class of this device, from component DEVICE_CLASSES."""
        return try_parse_enum(SensorDeviceClass, self._static_info.device_class)

    @property
    def state_class(self) -> SensorStateClass | None:
        """Return the state class of this entity."""
        if not self._static_info.state_class:
            return None
        state_class = self._static_info.state_class
        reset_type = self._static_info.last_reset_type
        if (
            state_class == EsphomeSensorStateClass.MEASUREMENT
            and reset_type == LastResetType.AUTO
        ):
            # Legacy, last_reset_type auto was the equivalent to the
            # TOTAL_INCREASING state class
            return SensorStateClass.TOTAL_INCREASING
        return _STATE_CLASSES.from_esphome(self._static_info.state_class)


class EsphomeTextSensor(EsphomeEntity[TextSensorInfo, TextSensorState], SensorEntity):
    """A text sensor implementation for ESPHome."""

    @property
    @esphome_state_property
    def native_value(self) -> str | None:
        """Return the state of the entity."""
        if self._state.missing_state:
            return None
        return self._state.state
