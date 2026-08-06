"""Platform for Schlage sensor integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from pyschlage.lock import Lock

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import LockData, SchlageConfigEntry, SchlageDataUpdateCoordinator
from .entity import SchlageEntity


@dataclass(frozen=True, kw_only=True)
class SchlageSensorEntityDescription(SensorEntityDescription):
    """Entity description for a Schlage sensor."""

    value_fn: Callable[[Lock], int | None]


_DESCRIPTIONS: tuple[SchlageSensorEntityDescription, ...] = (
    SchlageSensorEntityDescription(
        key="battery_level",
        device_class=SensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda lock: lock.battery_level,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: SchlageConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensors based on a config entry."""
    coordinator = config_entry.runtime_data

    def _add_new_locks(locks: dict[str, LockData]) -> None:
        async_add_entities(
            SchlageBatterySensor(
                coordinator=coordinator,
                description=description,
                device_id=device_id,
            )
            for description in _DESCRIPTIONS
            for device_id in locks
        )

    _add_new_locks(coordinator.data)
    coordinator.new_locks_callbacks.append(_add_new_locks)


class SchlageBatterySensor(SchlageEntity, SensorEntity):
    """Schlage battery sensor entity."""

    entity_description: SchlageSensorEntityDescription

    def __init__(
        self,
        coordinator: SchlageDataUpdateCoordinator,
        description: SchlageSensorEntityDescription,
        device_id: str,
    ) -> None:
        """Initialize a Schlage battery sensor."""
        super().__init__(coordinator=coordinator, device_id=device_id)
        self.entity_description = description
        self._attr_unique_id = f"{device_id}_{description.key}"

    @property
    @override
    def native_value(self) -> int | None:
        """Return the value reported by the sensor."""
        return self.entity_description.value_fn(self._lock)
