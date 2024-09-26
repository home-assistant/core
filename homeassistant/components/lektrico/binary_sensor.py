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
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import LektricoConfigEntry, LektricoDeviceDataUpdateCoordinator
from .entity import LektricoEntity


@dataclass(frozen=True, kw_only=True)
class LektricoBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes Lektrico binary sensor entity."""

    value_fn: Callable[[dict[str, Any]], bool]
    attributes_fn: Callable[[Any], dict[Any, bool]] | None = None


BINARY_SENSORS: tuple[LektricoBinarySensorEntityDescription, ...] = (
    LektricoBinarySensorEntityDescription(
        key="errors",
        translation_key="errors",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda data: bool(data["has_active_errors"]),
        attributes_fn=lambda data: {
            "state_e_activated": bool(data["state_e_activated"]),
            "overtemp": bool(data["overtemp"]),
            "critical_temp": bool(data["critical_temp"]),
            "overcurrent": bool(data["overcurrent"]),
            "meter_fault": bool(data["meter_fault"]),
            "undervoltage_error": bool(data["undervoltage_error"]),
            "overvoltage_error": bool(data["overvoltage_error"]),
            "rcd_error": bool(data["rcd_error"]),
            "cp_diode_failure": bool(data["cp_diode_failure"]),
            "contactor_failure": bool(data["contactor_failure"]),
        },
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

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update attributes when the coordinator updates."""
        if self.entity_description.attributes_fn is not None:
            self._attr_extra_state_attributes = self.entity_description.attributes_fn(
                self._coordinator.data
            )
            super()._handle_coordinator_update()
