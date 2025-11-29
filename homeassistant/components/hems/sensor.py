"""Sensor platform for the HEMS integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .definitions import DecoderSpec, EntityDefinition, NumericDecoderSpec
from .entity import HemsDescribedEntity, HemsEntityDescription, setup_hems_platform
from .types import HemsConfigEntry

PARALLEL_UPDATES = 0

# Mapping from JSON device_class to SensorDeviceClass
_SENSOR_DEVICE_CLASS_MAP: dict[str, SensorDeviceClass | None] = {
    "battery": SensorDeviceClass.BATTERY,
    "co2": SensorDeviceClass.CO2,
    "current": SensorDeviceClass.CURRENT,
    "energy": SensorDeviceClass.ENERGY,
    "humidity": SensorDeviceClass.HUMIDITY,
    "power": SensorDeviceClass.POWER,
    "temperature": SensorDeviceClass.TEMPERATURE,
    "voltage": SensorDeviceClass.VOLTAGE,
}

# Mapping from JSON state_class to SensorStateClass
_SENSOR_STATE_CLASS_MAP: dict[str, SensorStateClass | None] = {
    "measurement": SensorStateClass.MEASUREMENT,
    "total": SensorStateClass.TOTAL,
    "total_increasing": SensorStateClass.TOTAL_INCREASING,
}


@dataclass(frozen=True, kw_only=True)
class HemsSensorEntityDescription(SensorEntityDescription, HemsEntityDescription):
    """Entity description with EPC metadata."""

    decoder: Callable[[bytes], float | int | None]
    byte_offset: int  # Byte position in EDT (0-indexed)
    byte_count: int  # Number of bytes to read from EDT


def _create_sensor_description(
    class_code: int,
    entity_def: EntityDefinition,
    decoder_spec: DecoderSpec,
) -> HemsSensorEntityDescription:
    """Create a sensor entity description from an EntityDefinition."""
    assert isinstance(decoder_spec, NumericDecoderSpec)

    return HemsSensorEntityDescription(
        key=f"{entity_def.epc:02x}_{entity_def.byte_offset}",
        translation_key=entity_def.translation_key,
        class_code=class_code,
        epc=entity_def.epc,
        device_class=_SENSOR_DEVICE_CLASS_MAP.get(entity_def.device_class),
        native_unit_of_measurement=entity_def.unit,
        state_class=_SENSOR_STATE_CLASS_MAP.get(entity_def.state_class),
        decoder=decoder_spec.create_decoder(byte_offset=entity_def.byte_offset),
        byte_offset=entity_def.byte_offset,
        byte_count=entity_def.byte_count,
        manufacturer_code=entity_def.manufacturer_code,
        fallback_name=entity_def.fallback_name,
    )


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: HemsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up HEMS sensors from a config entry."""
    setup_hems_platform(
        entry,
        async_add_entities,
        "sensor",
        _create_sensor_description,
        HemsSensor,
        "sensor",
    )


class HemsSensor(HemsDescribedEntity[HemsSensorEntityDescription], SensorEntity):
    """Representation of a HEMS ECHONET sensor property."""

    @property
    def native_value(self) -> float | int | None:
        """Return the state of the sensor."""
        state = self._node.properties.get(self._epc)
        return self.description.decoder(state) if state is not None else None


__all__ = ["HemsSensor", "HemsSensorEntityDescription"]
