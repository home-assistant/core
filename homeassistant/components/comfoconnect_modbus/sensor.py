"""Support for Zehnder ComfoConnect PRO sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from comfoconnect_pro_modbus import ALARM_SLOTS, CO2_ZONES, AlarmCode, ComfoConnectPro

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfRatio,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import ComfoConnectProConfigEntry
from .entity import ComfoConnectProEntity, ComfoConnectProEntityDescription

PARALLEL_UPDATES = 0

NO_ALARM = "none"
ALARM_OPTIONS = [NO_ALARM, *(code.name.lower() for code in AlarmCode)]
# The room sensor is optional, so its two sensors are added separately.
AIR_STREAMS = ("extract", "exhaust", "outdoor", "supply")


@dataclass(frozen=True, kw_only=True)
class ComfoConnectProSensorDescription(
    SensorEntityDescription, ComfoConnectProEntityDescription
):
    """Describe a ComfoConnect PRO sensor."""

    value_fn: Callable[[ComfoConnectPro], StateType]


def _attribute(component: str, name: str) -> Callable[[ComfoConnectPro], StateType]:
    """Read ``name`` of ``component``."""

    def _value(device: ComfoConnectPro) -> StateType:
        value: StateType = getattr(getattr(device, component), name)
        return value

    return _value


def _temperature(stream: str) -> ComfoConnectProSensorDescription:
    """The temperature sensor of air stream ``stream``."""
    return ComfoConnectProSensorDescription(
        key=f"{stream}_temperature",
        translation_key=f"{stream}_temperature",
        component="sensors",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=_attribute("sensors", f"{stream}_temperature"),
    )


def _humidity(stream: str) -> ComfoConnectProSensorDescription:
    """The humidity sensor of air stream ``stream``."""
    return ComfoConnectProSensorDescription(
        key=f"{stream}_humidity",
        translation_key=f"{stream}_humidity",
        component="sensors",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_attribute("sensors", f"{stream}_humidity"),
    )


def _alarm(slot: int) -> Callable[[ComfoConnectPro], StateType]:
    """Read alarm slot ``slot`` as a sensor option."""

    def _value(device: ComfoConnectPro) -> StateType:
        code = device.status.active_error(slot)
        if code == 0:
            return NO_ALARM
        # Map an unread slot or a code the manual does not list to None
        return code.name.lower() if isinstance(code, AlarmCode) else None

    return _value


SENSOR_DESCRIPTIONS: tuple[ComfoConnectProSensorDescription, ...] = (
    ComfoConnectProSensorDescription(
        key="airflow",
        translation_key="airflow",
        component="sensors",
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        native_unit_of_measurement=UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_attribute("sensors", "airflow"),
    ),
    *(_temperature(stream) for stream in AIR_STREAMS),
    *(_humidity(stream) for stream in AIR_STREAMS),
    ComfoConnectProSensorDescription(
        key="filter_days_remaining",
        translation_key="filter_days_remaining",
        component="sensors",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.DAYS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_attribute("sensors", "filter_days_remaining"),
    ),
    ComfoConnectProSensorDescription(
        key="comfort_temperature",
        translation_key="comfort_temperature",
        component="controls",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=_attribute("controls", "comfort_temperature"),
    ),
    ComfoConnectProSensorDescription(
        key="boost_remaining",
        translation_key="boost_remaining",
        component="controls",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        value_fn=_attribute("controls", "boost_remaining"),
    ),
    *(
        ComfoConnectProSensorDescription(
            key=f"active_error_{slot}",
            translation_key="active_error",
            translation_placeholders={"number": str(slot)},
            component="status",
            device_class=SensorDeviceClass.ENUM,
            options=ALARM_OPTIONS,
            entity_category=EntityCategory.DIAGNOSTIC,
            entity_registry_enabled_default=slot == 1,
            value_fn=_alarm(slot),
        )
        for slot in range(1, ALARM_SLOTS + 1)
    ),
)


def co2_sensor(zone: int) -> ComfoConnectProSensorDescription:
    """The CO₂ sensor of ``zone``."""
    return ComfoConnectProSensorDescription(
        key=f"co2_zone_{zone}",
        translation_key="co2_zone",
        translation_placeholders={"number": str(zone)},
        component="sensors",
        device_class=SensorDeviceClass.CO2,
        native_unit_of_measurement=UnitOfRatio.PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
        # A zone whose sensor drops out reads 0, which is no measurement
        value_fn=lambda device: device.sensors.co2(zone) or None,
    )


# Sensors added the first time they report a value: the room sensor's two,
# which read nothing without a room sensor, and each CO₂ zone's.
OPTIONAL_SENSOR_DESCRIPTIONS: tuple[ComfoConnectProSensorDescription, ...] = (
    _temperature("room"),
    _humidity("room"),
    *(co2_sensor(zone) for zone in range(1, CO2_ZONES + 1)),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ComfoConnectProConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the ComfoConnect PRO sensor platform."""
    coordinator = entry.runtime_data
    added: set[str] = set()
    async_add_entities(
        ComfoConnectProSensor(coordinator, description)
        for description in SENSOR_DESCRIPTIONS
    )

    @callback
    def _async_add_optional_sensors() -> None:
        """Add an optional sensor the first time it reports a value."""
        new = [
            description
            for description in OPTIONAL_SENSOR_DESCRIPTIONS
            if description.key not in added
            and description.value_fn(coordinator.device) is not None
        ]
        if not new:
            return
        added.update(description.key for description in new)
        async_add_entities(
            ComfoConnectProSensor(coordinator, description) for description in new
        )

    _async_add_optional_sensors()
    entry.async_on_unload(coordinator.async_add_listener(_async_add_optional_sensors))


class ComfoConnectProSensor(ComfoConnectProEntity, SensorEntity):
    """Defines a ComfoConnect PRO sensor."""

    entity_description: ComfoConnectProSensorDescription

    @property
    @override
    def native_value(self) -> StateType:
        return self.entity_description.value_fn(self.coordinator.device)
