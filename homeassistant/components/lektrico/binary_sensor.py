"""Support for Lektrico binary sensors entities."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import ATTR_SERIAL_NUMBER, CONF_TYPE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import LektricoConfigEntry, LektricoDeviceDataUpdateCoordinator
from .entity import LektricoEntity


@dataclass(frozen=True, kw_only=True)
class LektricoBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes Lektrico binary sensor entity."""

    value_fn: Callable[[dict[str, Any]], bool]


BINARY_SENSORS: tuple[LektricoBinarySensorEntityDescription, ...] = (
    LektricoBinarySensorEntityDescription(
        key="state_e_activated",
        translation_key="state_e_activated",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda data: bool(data["state_e_activated"]),
    ),
    LektricoBinarySensorEntityDescription(
        key="overtemp",
        translation_key="overtemp",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda data: bool(data["overtemp"]),
    ),
    LektricoBinarySensorEntityDescription(
        key="critical_temp",
        translation_key="critical_temp",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda data: bool(data["critical_temp"]),
    ),
    LektricoBinarySensorEntityDescription(
        key="overcurrent",
        translation_key="overcurrent",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda data: bool(data["overcurrent"]),
    ),
    LektricoBinarySensorEntityDescription(
        key="meter_fault",
        translation_key="meter_fault",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda data: bool(data["meter_fault"]),
    ),
    LektricoBinarySensorEntityDescription(
        key="undervoltage",
        translation_key="undervoltage",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda data: bool(data["undervoltage_error"]),
    ),
    LektricoBinarySensorEntityDescription(
        key="overvoltage",
        translation_key="overvoltage",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda data: bool(data["overvoltage_error"]),
    ),
    LektricoBinarySensorEntityDescription(
        key="rcd_error",
        translation_key="rcd_error",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda data: bool(data["rcd_error"]),
    ),
    LektricoBinarySensorEntityDescription(
        key="cp_diode_failure",
        translation_key="cp_diode_failure",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda data: bool(data["cp_diode_failure"]),
    ),
    LektricoBinarySensorEntityDescription(
        key="contactor_failure",
        translation_key="contactor_failure",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda data: bool(data["contactor_failure"]),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LektricoConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Lektrico binary sensor entities based on a config entry."""
    coordinator = entry.runtime_data

    async_add_entities(
        LektricoBinarySensor(
            description,
            coordinator,
            f"{entry.data[CONF_TYPE]}_{entry.data[ATTR_SERIAL_NUMBER]}",
        )
        for description in BINARY_SENSORS
    )


class LektricoBinarySensor(LektricoEntity, BinarySensorEntity):
    """Defines a Lektrico binary sensor entity."""

    entity_description: LektricoBinarySensorEntityDescription

    def __init__(
        self,
        description: LektricoBinarySensorEntityDescription,
        coordinator: LektricoDeviceDataUpdateCoordinator,
        device_name: str,
    ) -> None:
        """Initialize Lektrico binary sensor."""
        super().__init__(coordinator, device_name)
        self.entity_description = description
        self._coordinator = coordinator
        self._attr_unique_id = f"{coordinator.serial_number}_{description.key}"

    @property
    def is_on(self) -> bool:
        """Return the state of the binary sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
