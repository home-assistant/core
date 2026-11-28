"""Support for OpenAQ sensors."""

from typing import override

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, DOMAIN, PARAMETER_DEVICE_CLASSES
from .coordinator import OpenAQConfigEntry, OpenAQDataUpdateCoordinator

PARALLEL_UPDATES = 0

SENSOR_DESCRIPTIONS: dict[str, SensorEntityDescription] = {
    parameter: SensorEntityDescription(
        key=parameter,
        device_class=device_class,
        translation_key=parameter if device_class is None else None,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2 if parameter == "co" else 1,
    )
    for parameter, device_class in PARAMETER_DEVICE_CLASSES.items()
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OpenAQConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up OpenAQ sensors."""
    for subentry_id, coordinator in entry.runtime_data.coordinators.items():
        async_add_entities(
            [
                OpenAQSensor(coordinator, SENSOR_DESCRIPTIONS[parameter])
                for parameter in coordinator.data.sensor_metadata
            ],
            config_subentry_id=subentry_id,
        )


class OpenAQSensor(CoordinatorEntity[OpenAQDataUpdateCoordinator], SensorEntity):
    """Representation of an OpenAQ sensor."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: OpenAQDataUpdateCoordinator,
        entity_description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = f"{coordinator.location_id}_{entity_description.key}"
        self._attr_native_unit_of_measurement = coordinator.data.sensor_metadata[
            entity_description.key
        ]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(coordinator.location_id))},
            name=coordinator.data.name,
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    @override
    def native_value(self) -> StateType:
        """Return the sensor value."""
        return self.coordinator.data.measurements.get(self.entity_description.key)
