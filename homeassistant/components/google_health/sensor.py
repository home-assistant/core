"""Sensor platform for the Google Health integration."""

from typing import override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import GoogleHealthConfigEntry
from .const import DOMAIN
from .coordinator import GoogleHealthActivityCoordinator, GoogleHealthBodyCoordinator

STEPS_SENSOR_DESCRIPTION = SensorEntityDescription(
    key="steps",
    translation_key="steps",
    native_unit_of_measurement="steps",
    icon="mdi:walk",
    state_class=SensorStateClass.TOTAL_INCREASING,
)

WEIGHT_SENSOR_DESCRIPTION = SensorEntityDescription(
    key="weight",
    translation_key="weight",
    native_unit_of_measurement="kg",
    device_class=SensorDeviceClass.WEIGHT,
    state_class=SensorStateClass.MEASUREMENT,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GoogleHealthConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Google Health sensor platform."""
    data = entry.runtime_data

    entities: list[SensorEntity] = []
    if data.activity_coordinator is not None:
        entities.append(
            GoogleHealthStepsSensor(
                data.activity_coordinator,
                entry.entry_id,
                entry.title,
                STEPS_SENSOR_DESCRIPTION,
            )
        )
    if data.body_coordinator is not None:
        entities.append(
            GoogleHealthWeightSensor(
                data.body_coordinator,
                entry.entry_id,
                entry.title,
                WEIGHT_SENSOR_DESCRIPTION,
            )
        )

    if entities:
        async_add_entities(entities)


class GoogleHealthStepsSensor(
    CoordinatorEntity[GoogleHealthActivityCoordinator], SensorEntity
):
    """Steps sensor entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: GoogleHealthActivityCoordinator,
        entry_id: str,
        entry_title: str,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the steps sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name=entry_title,
            manufacturer="Google",
        )

    @property
    @override
    def native_value(self) -> int:
        """Return the steps count."""
        return self.coordinator.data


class GoogleHealthWeightSensor(
    CoordinatorEntity[GoogleHealthBodyCoordinator], SensorEntity
):
    """Weight sensor entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: GoogleHealthBodyCoordinator,
        entry_id: str,
        entry_title: str,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the weight sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name=entry_title,
            manufacturer="Google",
        )

    @property
    @override
    def native_value(self) -> float | None:
        """Return the body weight."""
        return self.coordinator.data
