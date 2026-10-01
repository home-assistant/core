"""Platform for the opengarage.io sensor component."""

import logging
from typing import cast, override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfLength,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import OpenGarageConfigEntry
from .entity import (
    OpenGarageCapabilityEntity,
    OpenGarageEntity,
    async_add_capability_entities,
)

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="dist",
        native_unit_of_measurement=UnitOfLength.CENTIMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="rssi",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="temp",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="humid",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OpenGarageConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the OpenGarage sensors."""
    open_garage_data_coordinator = entry.runtime_data
    async_add_entities(
        OpenGarageSensor(
            open_garage_data_coordinator,
            cast(str, entry.unique_id),
            description,
        )
        for description in SENSOR_TYPES
        if description.key in open_garage_data_coordinator.data.raw
    )

    async_add_capability_entities(
        entry.runtime_data,
        async_add_entities,
        {
            "openings_counter": lambda: OpenGarageOpeningsSensor(
                entry.runtime_data,
                cast(str, entry.unique_id),
                SensorEntityDescription(
                    key="nopenings",
                    translation_key="openings",
                    entity_category=EntityCategory.DIAGNOSTIC,
                    entity_registry_enabled_default=False,
                    state_class=SensorStateClass.TOTAL_INCREASING,
                ),
            )
        },
    )


class OpenGarageSensor(OpenGarageEntity, SensorEntity):
    """Representation of a OpenGarage sensor."""

    @callback
    @override
    def _update_attr(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_native_value = self.coordinator.data.raw.get(
            self.entity_description.key
        )


class OpenGarageOpeningsSensor(OpenGarageCapabilityEntity, SensorEntity):
    """Representation of the opener's reported openings counter."""

    capability = "openings_counter"

    @callback
    @override
    def _update_attr(self) -> None:
        """Update the number of openings."""
        self._attr_native_value = self.coordinator.data.nopenings
