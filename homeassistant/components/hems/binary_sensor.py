"""Binary sensor platform for the HEMS integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .definitions import BinaryDecoderSpec, DecoderSpec, EntityDefinition
from .entity import HemsDescribedEntity, HemsEntityDescription, setup_hems_platform
from .types import HemsConfigEntry

PARALLEL_UPDATES = 0


# Mapping from JSON device_class to BinarySensorDeviceClass
_BINARY_SENSOR_DEVICE_CLASS_MAP: dict[str, BinarySensorDeviceClass] = {
    "door": BinarySensorDeviceClass.DOOR,
    "gas": BinarySensorDeviceClass.GAS,
    "moisture": BinarySensorDeviceClass.MOISTURE,
    "motion": BinarySensorDeviceClass.MOTION,
    "occupancy": BinarySensorDeviceClass.OCCUPANCY,
    "power": BinarySensorDeviceClass.POWER,
    "smoke": BinarySensorDeviceClass.SMOKE,
    "window": BinarySensorDeviceClass.WINDOW,
}


@dataclass(frozen=True, kw_only=True)
class HemsBinarySensorEntityDescription(
    BinarySensorEntityDescription, HemsEntityDescription
):
    """Entity description that tracks EPC metadata."""

    decoder: Callable[[bytes], bool | None]
    require_write: bool | None = False  # Binary sensor: readable but NOT writable


def _create_binary_sensor_description(
    class_code: int,
    entity_def: EntityDefinition,
    decoder_spec: DecoderSpec,
) -> HemsBinarySensorEntityDescription:
    """Create a binary sensor entity description from an EntityDefinition."""
    assert isinstance(decoder_spec, BinaryDecoderSpec)

    return HemsBinarySensorEntityDescription(
        key=f"{entity_def.epc:02x}",
        translation_key=entity_def.translation_key,
        class_code=class_code,
        epc=entity_def.epc,
        device_class=_BINARY_SENSOR_DEVICE_CLASS_MAP.get(entity_def.device_class),
        decoder=decoder_spec.create_decoder(),
        manufacturer_code=entity_def.manufacturer_code,
        fallback_name=entity_def.fallback_name,
    )


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: HemsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up HEMS binary sensors from a config entry."""
    setup_hems_platform(
        entry,
        async_add_entities,
        "binary",
        _create_binary_sensor_description,
        HemsBinarySensor,
        "binary_sensor",
    )


class HemsBinarySensor(
    HemsDescribedEntity[HemsBinarySensorEntityDescription], BinarySensorEntity
):
    """Representation of a boolean ECHONET Lite property."""

    @property
    def is_on(self) -> bool | None:
        """Return the state of the binary sensor."""
        state = self._node.properties.get(self._epc)
        return self.description.decoder(state) if state else None


__all__ = ["HemsBinarySensor", "HemsBinarySensorEntityDescription"]
