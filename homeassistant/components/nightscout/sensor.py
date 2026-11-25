"""Support for Nightscout sensors."""

from typing import Any, override

from py_nightscout.models import ServerStatus

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    ATTR_DATE,
    CONF_URL,
    EntityCategory,
    UnitOfBloodGlucoseConcentration,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTR_DELTA, ATTR_DEVICE, ATTR_DIRECTION, DOMAIN
from .coordinator import (
    NightscoutConfigEntry,
    NightscoutGlucoseCoordinator,
    NightscoutStatusCoordinator,
)

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0

DEFAULT_NAME = "Blood Glucose"

TREND_ICONS = {
    "Flat": "mdi:arrow-right",
    "SingleDown": "mdi:arrow-down",
    "FortyFiveDown": "mdi:arrow-bottom-right",
    "DoubleDown": "mdi:chevron-triple-down",
    "SingleUp": "mdi:arrow-up",
    "FortyFiveUp": "mdi:arrow-top-right",
    "DoubleUp": "mdi:chevron-triple-up",
}

# Nightscout always reports thresholds in mg/dL, even on mmol/L sites
THRESHOLD_SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="bgHigh",
        translation_key="urgent_high_threshold",
        device_class=SensorDeviceClass.BLOOD_GLUCOSE_CONCENTRATION,
        native_unit_of_measurement=UnitOfBloodGlucoseConcentration.MILLIGRAMS_PER_DECILITER,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="bgTargetTop",
        translation_key="target_range_top",
        device_class=SensorDeviceClass.BLOOD_GLUCOSE_CONCENTRATION,
        native_unit_of_measurement=UnitOfBloodGlucoseConcentration.MILLIGRAMS_PER_DECILITER,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="bgTargetBottom",
        translation_key="target_range_bottom",
        device_class=SensorDeviceClass.BLOOD_GLUCOSE_CONCENTRATION,
        native_unit_of_measurement=UnitOfBloodGlucoseConcentration.MILLIGRAMS_PER_DECILITER,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="bgLow",
        translation_key="urgent_low_threshold",
        device_class=SensorDeviceClass.BLOOD_GLUCOSE_CONCENTRATION,
        native_unit_of_measurement=UnitOfBloodGlucoseConcentration.MILLIGRAMS_PER_DECILITER,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


def _get_thresholds(status: ServerStatus) -> dict[str, Any] | None:
    """Return the thresholds from the server status settings."""
    thresholds: dict[str, Any] | None = (status.settings or {}).get("thresholds")
    return thresholds


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NightscoutConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Glucose Sensor."""
    glucose_coordinator = entry.runtime_data.glucose
    status_coordinator = entry.runtime_data.status
    entities: list[SensorEntity] = [
        NightscoutSensor(glucose_coordinator, "Blood Sugar", entry.unique_id)
    ]
    if _get_thresholds(status_coordinator.data) is not None:
        entities.extend(
            NightscoutThresholdSensor(status_coordinator, description)
            for description in THRESHOLD_SENSORS
        )
    async_add_entities(entities)


class NightscoutSensor(CoordinatorEntity[NightscoutGlucoseCoordinator], SensorEntity):
    """Implementation of a Nightscout sensor."""

    _attr_device_class = SensorDeviceClass.BLOOD_GLUCOSE_CONCENTRATION
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = (
        UnitOfBloodGlucoseConcentration.MILLIGRAMS_PER_DECILITER
    )

    def __init__(
        self,
        coordinator: NightscoutGlucoseCoordinator,
        name: str,
        unique_id: str | None,
    ) -> None:
        """Initialize the Nightscout sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = unique_id
        self._attr_name = name

    @property
    @override
    def available(self) -> bool:
        """Return if a glucose reading is available."""
        return super().available and self.coordinator.data is not None

    @property
    @override
    def native_value(self) -> int | None:
        """Return the latest glucose value."""
        reading = self.coordinator.data
        return int(reading.sgv) if reading else None

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the attributes of the latest glucose reading."""
        reading = self.coordinator.data
        return (
            {
                ATTR_DEVICE: reading.device,
                ATTR_DATE: reading.date,
                ATTR_DELTA: reading.delta,
                ATTR_DIRECTION: reading.direction,
            }
            if reading
            else None
        )

    @property
    @override
    def icon(self) -> str:
        """Return an icon matching the trend direction."""
        reading = self.coordinator.data
        if reading is None:
            return "mdi:cloud-question"
        return TREND_ICONS.get(reading.direction, "mdi:cloud-question")


class NightscoutThresholdSensor(
    CoordinatorEntity[NightscoutStatusCoordinator], SensorEntity
):
    """A glucose threshold configured on the Nightscout server."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: NightscoutStatusCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the threshold sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        entry = coordinator.config_entry
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.data[CONF_URL])}
        )

    @property
    @override
    def native_value(self) -> float | None:
        """Return the threshold value."""
        thresholds = _get_thresholds(self.coordinator.data) or {}
        value: float | None = thresholds.get(self.entity_description.key)
        return value
