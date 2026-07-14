"""WATERCryst BIOCAT device sensors."""

from operator import attrgetter
from typing import Any, override

from homeassistant.components.sensor import (
    HomeAssistant,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    UnitOfPressure,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolume,
    UnitOfVolumeFlowRate,
)
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from . import WatercrystConfigEntry
from .coordinator import MeasurementsUpdateCoordinator, StateUpdateCoordinator
from .entity import WatercrystEntity

MEASUREMENT_SENSORS = [
    SensorEntityDescription(
        key="water_temp",
        translation_key="water_temp",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=0,
    ),
    SensorEntityDescription(
        key="pressure",
        translation_key="pressure",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.BAR,
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key="flow_rate",
        translation_key="flow_rate",
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        native_unit_of_measurement=UnitOfVolumeFlowRate.LITERS_PER_MINUTE,
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key="last_water_tap_volume",
        translation_key="last_water_tap_volume",
        icon="mdi:cup-water",
        device_class=SensorDeviceClass.WATER,
        native_unit_of_measurement=UnitOfVolume.LITERS,
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key="last_water_tap_duration",
        translation_key="last_water_tap_duration",
        icon="mdi:timer-outline",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_display_precision=0,
    ),
]

STATE_SENSORS = [
    SensorEntityDescription(
        key="mode.id", translation_key="mode_id", icon="mdi:circle-double"
    ),
    SensorEntityDescription(
        key="ml_state", translation_key="ml_state", icon="mdi:pipe-leak"
    ),
    SensorEntityDescription(
        key="water_protection.pause_leakage_protection_until_utc",
        translation_key="pause_leakage_protection_until_utc",
        icon="mdi:pause-circle-outline",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
]

EVENT_SENSORS = [
    SensorEntityDescription(
        key="event.event_id",
        translation_key="event_id",
        icon="mdi:alert-circle-outline",
    ),
    SensorEntityDescription(
        key="event.category",
        translation_key="event_category",
        icon="mdi:alert-circle-outline",
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: WatercrystConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensor entities."""
    async_add_entities(
        WatercrystMeasurementSensorEntity(config_entry, description)
        for description in MEASUREMENT_SENSORS
    )
    async_add_entities(
        WatercrystStateSensorEntity(config_entry, description)
        for description in STATE_SENSORS
    )
    async_add_entities(
        WatercrystEventSensorEntity(config_entry, description)
        for description in EVENT_SENSORS
    )


class WatercrystSensorEntity[_T: DataUpdateCoordinator[Any]](
    CoordinatorEntity[_T], SensorEntity, WatercrystEntity
):
    """BIOCAT device sensor base class."""

    def __init__(
        self,
        config_entry: WatercrystConfigEntry,
        coordinator: _T,
        entity_description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        CoordinatorEntity.__init__(self, coordinator)
        WatercrystEntity.__init__(self, config_entry, entity_description)

    @override
    @property
    def native_value(self) -> StateType:
        """Dynamically fetch the attribute value."""
        if self.coordinator.data is None:
            return None
        getter = attrgetter(self.entity_description.key)
        return getter(self.coordinator.data)


class WatercrystMeasurementSensorEntity(
    WatercrystSensorEntity[MeasurementsUpdateCoordinator]
):
    """Measurements sensor entity."""

    def __init__(
        self,
        config_entry: WatercrystConfigEntry,
        entity_description: SensorEntityDescription,
    ) -> None:
        """Initialize a WatercrystMeasurementSensorEntity instance."""
        super().__init__(
            config_entry=config_entry,
            coordinator=config_entry.runtime_data.measurements,
            entity_description=entity_description,
        )


class WatercrystStateSensorEntity(WatercrystSensorEntity[StateUpdateCoordinator]):
    """State sensor entity."""

    def __init__(
        self,
        config_entry: WatercrystConfigEntry,
        entity_description: SensorEntityDescription,
    ) -> None:
        """Initialize a WatercrystStateSensorEntity instance."""
        super().__init__(
            config_entry=config_entry,
            coordinator=config_entry.runtime_data.state,
            entity_description=entity_description,
        )


class WatercrystEventSensorEntity(WatercrystStateSensorEntity):
    """Event sensor entity."""

    @override
    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Provide all event properties as extra state attributes.

        Attributes:
        -----------
        event_id : int
            Identifies the type of the event.
        category : Literal['error', 'warning', 'info']
            The event category.
        title : str
            Event summary.
        description : str
            Detailed description.
        timestamp : datetime
            UTC date time of the event.
        """
        if not self.coordinator.data:
            return None
        return self.coordinator.data.event.model_dump()
