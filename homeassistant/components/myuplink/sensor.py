"""Sensor for myUplink."""

from myuplink import DevicePoint

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    REVOLUTIONS_PER_MINUTE,
    Platform,
    UnitOfElectricCurrent,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfPressure,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import MyUplinkConfigEntry, MyUplinkDataCoordinator
from .entity import MyUplinkEntity
from .helpers import find_matching_platform, skip_entity

DEVICE_POINT_UNIT_DESCRIPTIONS: dict[str, SensorEntityDescription] = {
    "°C": SensorEntityDescription(
        key="celsius",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    "°F": SensorEntityDescription(
        key="fahrenheit",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
    ),
    "A": SensorEntityDescription(
        key="ampere",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
    ),
    "bar": SensorEntityDescription(
        key="pressure",
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPressure.BAR,
    ),
    "days": SensorEntityDescription(
        key="days",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.DAYS,
        suggested_display_precision=0,
    ),
    "h": SensorEntityDescription(
        key="hours",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.HOURS,
        suggested_display_precision=1,
    ),
    "hrs": SensorEntityDescription(
        key="hours_hrs",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.HOURS,
        suggested_display_precision=1,
    ),
    "Hz": SensorEntityDescription(
        key="hertz",
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
    ),
    "kW": SensorEntityDescription(
        key="power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
    ),
    "kWh": SensorEntityDescription(
        key="energy",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
    ),
    "m3/h": SensorEntityDescription(
        key="airflow",
        translation_key="airflow",
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
    ),
    "min": SensorEntityDescription(
        key="minutes",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
    ),
    "Pa": SensorEntityDescription(
        key="pressure_pa",
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPressure.PA,
        suggested_display_precision=0,
    ),
    "rpm": SensorEntityDescription(
        key="rpm",
        translation_key="rpm",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
        suggested_display_precision=0,
    ),
    "s": SensorEntityDescription(
        key="seconds",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_display_precision=0,
    ),
    "sec": SensorEntityDescription(
        key="seconds_sec",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_display_precision=0,
    ),
}

MARKER_FOR_UNKNOWN_VALUE = -32768

CATEGORY_BASED_DESCRIPTIONS: dict[str, dict[str, SensorEntityDescription]] = {
    "NIBEF": {
        "43108": SensorEntityDescription(
            key="fan_mode",
            translation_key="fan_mode",
        ),
        "43427": SensorEntityDescription(
            key="status_compressor",
            translation_key="status_compressor",
            device_class=SensorDeviceClass.ENUM,
        ),
        "49993": SensorEntityDescription(
            key="elect_add",
            translation_key="elect_add",
            device_class=SensorDeviceClass.ENUM,
        ),
        "49994": SensorEntityDescription(
            key="priority",
            translation_key="priority",
            device_class=SensorDeviceClass.ENUM,
        ),
    },
    "NIBE": {},
}


def get_description(device_point: DevicePoint) -> SensorEntityDescription | None:
    """Get description for a device point.

    Priorities:
    1. Category specific prefix e.g "NIBEF"
    2. Global parameter_unit e.g. "°C"
    3. Default to None
    """
    description = None
    prefix, _, _ = device_point.category.partition(" ")
    description = CATEGORY_BASED_DESCRIPTIONS.get(prefix, {}).get(
        device_point.parameter_id
    )
    if description is None:
        description = DEVICE_POINT_UNIT_DESCRIPTIONS.get(device_point.parameter_unit)

    return description


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MyUplinkConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up myUplink sensor."""

    entities: list[SensorEntity] = []
    coordinator = config_entry.runtime_data

    # Setup device point sensors
    for device_id, point_data in coordinator.data.points.items():
        for point_id, device_point in point_data.items():
            if skip_entity(device_point.category, device_point):
                continue
            if find_matching_platform(device_point) == Platform.SENSOR:
                description = get_description(device_point)
                entity_class = MyUplinkDevicePointSensor
                # Ignore sensors without a description that provide non-numeric values
                if description is None and not isinstance(
                    device_point.value, (int, float)
                ):
                    continue
                if (
                    description is not None
                    and description.device_class == SensorDeviceClass.ENUM
                ):
                    entities.append(
                        MyUplinkEnumRawSensor(
                            coordinator=coordinator,
                            device_id=device_id,
                            device_point=device_point,
                            entity_description=description,
                            unique_id_suffix=f"{point_id}-raw",
                        )
                    )
                    entity_class = MyUplinkEnumSensor

                entities.append(
                    entity_class(
                        coordinator=coordinator,
                        device_id=device_id,
                        device_point=device_point,
                        entity_description=description,
                        unique_id_suffix=point_id,
                    )
                )

    async_add_entities(entities)


class MyUplinkDevicePointSensor(MyUplinkEntity, SensorEntity):
    """Representation of a myUplink device point sensor."""

    def __init__(
        self,
        coordinator: MyUplinkDataCoordinator,
        device_id: str,
        device_point: DevicePoint,
        entity_description: SensorEntityDescription | None,
        unique_id_suffix: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(
            coordinator=coordinator,
            device_id=device_id,
            unique_id_suffix=unique_id_suffix,
        )

        # Internal properties
        self.point_id = device_point.parameter_id
        # Remove soft hyphens
        self._attr_name = device_point.parameter_name.replace("\u00ad", "")

        if entity_description is not None:
            self.entity_description = entity_description
        else:
            self._attr_native_unit_of_measurement = device_point.parameter_unit

    @property
    def native_value(self) -> StateType:
        """Sensor state value."""
        device_point = self.coordinator.data.points[self.device_id][self.point_id]
        if device_point.value == MARKER_FOR_UNKNOWN_VALUE:
            return None
        return device_point.value  # type: ignore[no-any-return]


class MyUplinkEnumSensor(MyUplinkDevicePointSensor):
    """Representation of a myUplink device point sensor for ENUM device_class."""

    def __init__(
        self,
        coordinator: MyUplinkDataCoordinator,
        device_id: str,
        device_point: DevicePoint,
        entity_description: SensorEntityDescription | None,
        unique_id_suffix: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(
            coordinator=coordinator,
            device_id=device_id,
            device_point=device_point,
            entity_description=entity_description,
            unique_id_suffix=unique_id_suffix,
        )

        self._attr_options = [x["text"].capitalize() for x in device_point.enum_values]
        self.options_map = {
            x["value"]: x["text"].capitalize() for x in device_point.enum_values
        }

    @property
    def native_value(self) -> str:
        """Sensor state value for enum sensor."""
        device_point = self.coordinator.data.points[self.device_id][self.point_id]
        return self.options_map[str(int(device_point.value))]  # type: ignore[no-any-return]


class MyUplinkEnumRawSensor(MyUplinkDevicePointSensor):
    """Representation of a myUplink device point sensor for raw value from ENUM device_class."""

    _attr_entity_registry_enabled_default = False
    _attr_device_class = None

    def __init__(
        self,
        coordinator: MyUplinkDataCoordinator,
        device_id: str,
        device_point: DevicePoint,
        entity_description: SensorEntityDescription | None,
        unique_id_suffix: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(
            coordinator=coordinator,
            device_id=device_id,
            device_point=device_point,
            entity_description=entity_description,
            unique_id_suffix=unique_id_suffix,
        )

        self._attr_name = f"{device_point.parameter_name} raw"
