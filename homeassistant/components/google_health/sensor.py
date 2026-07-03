"""Sensor platform for the Google Health integration."""

from typing import override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfLength, UnitOfMass
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
    state_class=SensorStateClass.TOTAL_INCREASING,
)

DISTANCE_SENSOR_DESCRIPTION = SensorEntityDescription(
    key="distance",
    native_unit_of_measurement=UnitOfLength.METERS,
    device_class=SensorDeviceClass.DISTANCE,
    state_class=SensorStateClass.TOTAL_INCREASING,
)

WEIGHT_SENSOR_DESCRIPTION = SensorEntityDescription(
    key="weight",
    native_unit_of_measurement=UnitOfMass.KILOGRAMS,
    device_class=SensorDeviceClass.WEIGHT,
    state_class=SensorStateClass.MEASUREMENT,
)

RESTING_HEART_RATE_SENSOR_DESCRIPTION = SensorEntityDescription(
    key="resting_heart_rate",
    translation_key="resting_heart_rate",
    native_unit_of_measurement="bpm",
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
        entities.extend(
            [
                GoogleHealthStepsSensor(
                    data.activity_coordinator,
                    entry.entry_id,
                    entry.title,
                    STEPS_SENSOR_DESCRIPTION,
                ),
                GoogleHealthDistanceSensor(
                    data.activity_coordinator,
                    entry.entry_id,
                    entry.title,
                    DISTANCE_SENSOR_DESCRIPTION,
                ),
            ]
        )
    if data.body_coordinator is not None:
        entities.extend(
            [
                GoogleHealthWeightSensor(
                    data.body_coordinator,
                    entry.entry_id,
                    entry.title,
                    WEIGHT_SENSOR_DESCRIPTION,
                ),
                GoogleHealthRestingHeartRateSensor(
                    data.body_coordinator,
                    entry.entry_id,
                    entry.title,
                    RESTING_HEART_RATE_SENSOR_DESCRIPTION,
                ),
            ]
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
        if self.coordinator.data is None or self.coordinator.data.steps is None:
            return 0
        return self.coordinator.data.steps.count_sum


class GoogleHealthDistanceSensor(
    CoordinatorEntity[GoogleHealthActivityCoordinator], SensorEntity
):
    """Distance sensor entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: GoogleHealthActivityCoordinator,
        entry_id: str,
        entry_title: str,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the distance sensor."""
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
    def native_value(self) -> float:
        """Return the daily distance in meters."""
        if self.coordinator.data is None or self.coordinator.data.distance is None:
            return 0.0
        return self.coordinator.data.distance.millimeters_sum / 1000.0


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
        if self.coordinator.data is None or self.coordinator.data.weight is None:
            return None
        return self.coordinator.data.weight.weight_grams / 1000.0


class GoogleHealthRestingHeartRateSensor(
    CoordinatorEntity[GoogleHealthBodyCoordinator], SensorEntity
):
    """Resting heart rate sensor entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: GoogleHealthBodyCoordinator,
        entry_id: str,
        entry_title: str,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the resting heart rate sensor."""
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
    def native_value(self) -> int | None:
        """Return the resting heart rate."""
        if (
            self.coordinator.data is None
            or self.coordinator.data.resting_heart_rate is None
        ):
            return None
        return self.coordinator.data.resting_heart_rate.beats_per_minute
