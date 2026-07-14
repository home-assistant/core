"""Sensor platform for LinknLink."""

from typing import override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    LIGHT_LUX,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfLength,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import LinknLinkConfigEntry, LinknLinkCoordinator
from .entity import LinknLinkEntity

PARALLEL_UPDATES = 0

SENSOR_DESCRIPTIONS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="envtemp",
        translation_key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="envhumid",
        translation_key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="envlux",
        translation_key="illuminance",
        device_class=SensorDeviceClass.ILLUMINANCE,
        native_unit_of_measurement=LIGHT_LUX,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="distance",
        translation_key="distance",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.CENTIMETERS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="target_distance",
        translation_key="target_distance",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.CENTIMETERS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="target_count",
        translation_key="target_count",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="persons_in_fenced_zones",
        translation_key="persons_in_fenced_zones",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="detect_position",
        translation_key="detect_position",
    ),
    SensorEntityDescription(
        key="wifi_rssi",
        translation_key="wifi_rssi",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LinknLinkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up LinknLink sensors."""
    coordinator = entry.runtime_data
    entities: list[LinknLinkSensor] = [
        LinknLinkSensor(coordinator, description)
        for description in SENSOR_DESCRIPTIONS
        if description.key in coordinator.data.values
    ]
    entities.extend(
        LinknLinkSensor(coordinator, description, subdevice_id)
        for subdevice_id, child in coordinator.data.children.items()
        for description in SENSOR_DESCRIPTIONS
        if description.key in child.fields
    )
    async_add_entities(entities)


class LinknLinkSensor(LinknLinkEntity, SensorEntity):
    """Representation of a LinknLink sensor."""

    entity_description: SensorEntityDescription

    def __init__(
        self,
        coordinator: LinknLinkCoordinator,
        description: SensorEntityDescription,
        subdevice_id: str | None = None,
    ) -> None:
        """Initialize a LinknLink sensor."""
        super().__init__(coordinator, description, subdevice_id)

    @property
    @override
    def native_value(self) -> StateType:
        """Return the sensor value."""
        value = self.source_value
        if value is None or isinstance(value, (bool, str, int, float)):
            return value
        return str(value)
