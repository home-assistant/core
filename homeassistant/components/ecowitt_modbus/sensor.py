"""What the sensor arrays measure."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, override

from ecowitt_modbus import WN69LP, WN90LP

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    DEGREE,
    LIGHT_LUX,
    PERCENTAGE,
    UV_INDEX,
    EntityCategory,
    UnitOfElectricPotential,
    UnitOfPrecipitationDepth,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import EcowittConfigEntry
from .entity import EcowittEntity, EcowittEntityDescription

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class EcowittSensorDescription(SensorEntityDescription, EcowittEntityDescription):
    """A sensor, and where to read its value off the device's readings."""

    value_fn: Callable[[Any], StateType]


def _reading(key: str, **kwargs: Any) -> EcowittSensorDescription:
    """Describe a sensor read straight off the device's live readings.

    Every model exposes its readings the same way -- as attributes of a
    ``sensors`` component named after the reading -- so the lookup is
    derived from the key rather than spelled out per entry.
    """
    return EcowittSensorDescription(
        key=key,
        component="sensors",
        translation_key=key,
        value_fn=lambda sensors: getattr(sensors, key),
        **kwargs,
    )


LIGHT = _reading(
    "light",
    device_class=SensorDeviceClass.ILLUMINANCE,
    native_unit_of_measurement=LIGHT_LUX,
    state_class=SensorStateClass.MEASUREMENT,
)
TEMPERATURE = _reading(
    "temperature",
    device_class=SensorDeviceClass.TEMPERATURE,
    native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    state_class=SensorStateClass.MEASUREMENT,
)
HUMIDITY = _reading(
    "humidity",
    device_class=SensorDeviceClass.HUMIDITY,
    native_unit_of_measurement=PERCENTAGE,
    state_class=SensorStateClass.MEASUREMENT,
)
WIND_SPEED = _reading(
    "wind_speed",
    device_class=SensorDeviceClass.WIND_SPEED,
    native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
    state_class=SensorStateClass.MEASUREMENT,
)
GUST_SPEED = _reading(
    "gust_speed",
    device_class=SensorDeviceClass.WIND_SPEED,
    native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
    state_class=SensorStateClass.MEASUREMENT,
)
WIND_DIRECTION = _reading(
    "wind_direction",
    device_class=SensorDeviceClass.WIND_DIRECTION,
    native_unit_of_measurement=DEGREE,
    state_class=SensorStateClass.MEASUREMENT_ANGLE,
)
ABSOLUTE_PRESSURE = _reading(
    "absolute_pressure",
    device_class=SensorDeviceClass.PRESSURE,
    native_unit_of_measurement=UnitOfPressure.HPA,
    state_class=SensorStateClass.MEASUREMENT,
)


def _rainfall(key: str, *, precision: int, **kwargs: Any) -> EcowittSensorDescription:
    """Describe a cumulative rainfall total.

    Both models count up from the last reset rather than reporting a rate,
    and both can be reset by a command this integration does not send.

    ``precision`` has to match the register's own step, or the default
    display rounds away the reading's real resolution. Zero decimals is the
    worst case -- it rounds a single 0.254mm WN69LP tip to nothing -- but
    even one or two decimals would still round 0.254 to 0.3 or 0.25, hiding
    the sensor's actual increment rather than just losing precision on a
    large total. Three decimals is what it takes to show the true step.
    """
    return _reading(
        key,
        device_class=SensorDeviceClass.PRECIPITATION,
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=precision,
        **kwargs,
    )


# The WN90LP reports UV index in tenths; the WN69LP in whole numbers. Same
# quantity and unit, different resolution, so they differ only in the
# precision each is displayed at.
WN90LP_UV_INDEX = _reading(
    "uv_index",
    native_unit_of_measurement=UV_INDEX,
    state_class=SensorStateClass.MEASUREMENT,
    suggested_display_precision=1,
)
WN69LP_UV_INDEX = _reading(
    "uv_index",
    native_unit_of_measurement=UV_INDEX,
    state_class=SensorStateClass.MEASUREMENT,
    suggested_display_precision=0,
)

SENSOR_DESCRIPTIONS: dict[str, tuple[EcowittSensorDescription, ...]] = {
    WN90LP.MODEL: (
        LIGHT,
        WN90LP_UV_INDEX,
        TEMPERATURE,
        HUMIDITY,
        WIND_SPEED,
        GUST_SPEED,
        WIND_DIRECTION,
        _rainfall("rainfall", precision=1),
        ABSOLUTE_PRESSURE,
        # The same cumulative total as `rainfall`, read from a separate
        # register at 0.01mm instead of 0.1mm. Off by default because it
        # duplicates a sensor that is already there -- but the finer
        # resolution is the only reason to enable it, so it is shown.
        _rainfall(
            "rain_counter",
            precision=2,
            entity_registry_enabled_default=False,
        ),
    ),
    WN69LP.MODEL: (
        LIGHT,
        WN69LP_UV_INDEX,
        TEMPERATURE,
        HUMIDITY,
        WIND_SPEED,
        GUST_SPEED,
        WIND_DIRECTION,
        _rainfall("rainfall", precision=3),
        ABSOLUTE_PRESSURE,
        # The WN90LP archives these two in its history block; the WN69LP has
        # them as live registers, re-measured once a minute. Both need an
        # explicit precision: the voltage device class defaults to whole
        # volts, which would round a 3.12V battery to 3V and hide exactly
        # the drift these are worth watching for.
        _reading(
            "battery_voltage",
            device_class=SensorDeviceClass.VOLTAGE,
            native_unit_of_measurement=UnitOfElectricPotential.VOLT,
            state_class=SensorStateClass.MEASUREMENT,
            entity_category=EntityCategory.DIAGNOSTIC,
            suggested_display_precision=2,
        ),
        _reading(
            "supply_voltage",
            device_class=SensorDeviceClass.VOLTAGE,
            native_unit_of_measurement=UnitOfElectricPotential.VOLT,
            state_class=SensorStateClass.MEASUREMENT,
            entity_category=EntityCategory.DIAGNOSTIC,
            entity_registry_enabled_default=False,
            suggested_display_precision=1,
        ),
        # The specification does not say what period this covers, only that
        # the rainfall-reset command clears it alongside the total. Off by
        # default rather than shipping a reading whose meaning is unclear.
        _rainfall(
            "recent_rainfall",
            precision=3,
            entity_registry_enabled_default=False,
        ),
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EcowittConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Ecowitt Modbus sensor platform."""
    coordinator = entry.runtime_data
    async_add_entities(
        EcowittSensor(coordinator, description)
        for description in SENSOR_DESCRIPTIONS[coordinator.device.MODEL]
    )


class EcowittSensor(EcowittEntity, SensorEntity):
    """A read-only value off a sensor array's live readings."""

    entity_description: EcowittSensorDescription

    @property
    @override
    def native_value(self) -> StateType:
        """Return the value this sensor reads from the device."""
        component = getattr(self.coordinator.device, self.entity_description.component)
        return self.entity_description.value_fn(component)
