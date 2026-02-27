"""Binary sensor platform for madVR Envy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import MadvrEnvyEntity


@dataclass(frozen=True, kw_only=True)
class MadvrEnvyBinarySensorDescription(BinarySensorEntityDescription):
    value_fn: Any


BINARY_SENSORS: tuple[MadvrEnvyBinarySensorDescription, ...] = (
    MadvrEnvyBinarySensorDescription(
        key="signal_present",
        translation_key="signal_present",
        device_class=BinarySensorDeviceClass.POWER,
        value_fn=lambda data: data.get("signal_present"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities(
        [
            MadvrEnvyBinarySensor(entry.runtime_data.coordinator, description)
            for description in BINARY_SENSORS
        ]
    )


class MadvrEnvyBinarySensor(MadvrEnvyEntity, BinarySensorEntity):
    """madVR Envy binary sensor."""

    entity_description: MadvrEnvyBinarySensorDescription

    def __init__(self, coordinator, description: MadvrEnvyBinarySensorDescription) -> None:  # noqa: ANN001
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        value = self.entity_description.value_fn(self.data)
        if value is None:
            return None
        return bool(value)
