"""Support for OpenAQ sensors."""

from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfLength
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, DOMAIN
from .coordinator import OpenAQConfigEntry, OpenAQDataUpdateCoordinator

DISTANCE_FROM_HOME = "distance_from_home"


@dataclass(frozen=True, kw_only=True)
class OpenAQSensorEntityDescription(SensorEntityDescription):
    """Description for an OpenAQ sensor entity."""


SENSOR_DESCRIPTIONS: dict[str, OpenAQSensorEntityDescription] = {
    "pm1": OpenAQSensorEntityDescription(
        key="pm1",
        device_class=SensorDeviceClass.PM1,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    "pm25": OpenAQSensorEntityDescription(
        key="pm25",
        device_class=SensorDeviceClass.PM25,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    "pm10": OpenAQSensorEntityDescription(
        key="pm10",
        device_class=SensorDeviceClass.PM10,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    "co": OpenAQSensorEntityDescription(
        key="co",
        device_class=SensorDeviceClass.CO,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    "co2": OpenAQSensorEntityDescription(
        key="co2",
        device_class=SensorDeviceClass.CO2,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    "no2": OpenAQSensorEntityDescription(
        key="no2",
        device_class=SensorDeviceClass.NITROGEN_DIOXIDE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    "o3": OpenAQSensorEntityDescription(
        key="o3",
        device_class=SensorDeviceClass.OZONE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    "so2": OpenAQSensorEntityDescription(
        key="so2",
        device_class=SensorDeviceClass.SULPHUR_DIOXIDE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    "no": OpenAQSensorEntityDescription(
        key="no",
        device_class=SensorDeviceClass.NITROGEN_MONOXIDE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    "nox": OpenAQSensorEntityDescription(
        key="nox",
        translation_key="nox",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    "bc": OpenAQSensorEntityDescription(
        key="bc",
        translation_key="bc",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
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
                for parameter in coordinator.data.measurements
                if parameter in SENSOR_DESCRIPTIONS
            ]
            + [OpenAQDistanceSensor(coordinator)],
            config_subentry_id=subentry_id,
        )


def _device_info(coordinator: OpenAQDataUpdateCoordinator) -> DeviceInfo:
    """Return device info for an OpenAQ location."""
    return DeviceInfo(
        identifiers={(DOMAIN, str(coordinator.location_id))},
        name=coordinator.data.name,
        entry_type=DeviceEntryType.SERVICE,
    )


class OpenAQSensor(CoordinatorEntity[OpenAQDataUpdateCoordinator], SensorEntity):
    """Representation of an OpenAQ sensor."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True
    entity_description: OpenAQSensorEntityDescription

    def __init__(
        self,
        coordinator: OpenAQDataUpdateCoordinator,
        entity_description: OpenAQSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = f"{coordinator.location_id}_{entity_description.key}"
        self._attr_device_info = _device_info(coordinator)

    @property
    def native_value(self) -> StateType:
        """Return the sensor value."""
        measurement = self.coordinator.data.measurements.get(
            self.entity_description.key
        )
        return measurement.value if measurement is not None else None

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the native unit of measurement."""
        measurement = self.coordinator.data.measurements.get(
            self.entity_description.key
        )
        if measurement is None:
            return None
        return measurement.unit


class OpenAQDistanceSensor(SensorEntity):
    """Representation of a static OpenAQ distance sensor."""

    _attr_attribution = ATTRIBUTION
    _attr_device_class = SensorDeviceClass.DISTANCE
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False
    _attr_has_entity_name = True
    _attr_name = "Distance from Home Assistant"
    _attr_native_unit_of_measurement = UnitOfLength.KILOMETERS
    _attr_should_poll = False
    _attr_suggested_display_precision = 1
    _attr_translation_key = DISTANCE_FROM_HOME

    def __init__(self, coordinator: OpenAQDataUpdateCoordinator) -> None:
        """Initialize the sensor."""
        self._attr_unique_id = f"{coordinator.location_id}_{DISTANCE_FROM_HOME}"
        self._attr_device_info = _device_info(coordinator)
        distance_to_home = coordinator.data.distance_to_home
        self._attr_native_value = (
            None if distance_to_home is None else distance_to_home / 1000
        )
