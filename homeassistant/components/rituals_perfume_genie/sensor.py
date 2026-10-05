"""Support for Rituals Perfume Genie sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from ritualsgenie import Sensor

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import RitualsConfigEntry, RitualsData
from .entity import DiffuserEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class RitualsSensorEntityDescription(SensorEntityDescription):
    """Class describing Rituals sensor entities."""

    has_fn: Callable[[RitualsData], bool] = lambda _: True
    value_fn: Callable[[RitualsData], int | str | None]


ENTITY_DESCRIPTIONS = (
    RitualsSensorEntityDescription(
        key="battery_percentage",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        value_fn=lambda data: data.sensors.battery_percentage,
        has_fn=lambda data: data.hub.has_battery,
    ),
    RitualsSensorEntityDescription(
        key="fill",
        translation_key="fill",
        value_fn=lambda data: data.sensors.fill.title if data.sensors.fill else None,
        has_fn=lambda data: Sensor.FILL in data.hub.supported_sensors,
    ),
    RitualsSensorEntityDescription(
        key="perfume",
        translation_key="perfume",
        value_fn=lambda data: (
            data.sensors.perfume.title if data.sensors.perfume else None
        ),
    ),
    RitualsSensorEntityDescription(
        key="wifi_percentage",
        translation_key="wifi_percentage",
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda data: data.sensors.wifi_percentage,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: RitualsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the diffuser sensors."""
    coordinators = config_entry.runtime_data

    async_add_entities(
        RitualsSensorEntity(coordinator, description)
        for coordinator in coordinators.values()
        for description in ENTITY_DESCRIPTIONS
        if description.has_fn(coordinator.data)
    )


class RitualsSensorEntity(DiffuserEntity, SensorEntity):
    """Representation of a diffuser sensor."""

    entity_description: RitualsSensorEntityDescription
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    @override
    def native_value(self) -> str | int | None:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.coordinator.data)
