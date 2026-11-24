"""Sensors of WAFE heat recovery units."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from wafe_modbus import UnitState, WafeUnit

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    REVOLUTIONS_PER_MINUTE,
    UnitOfRatio,
    UnitOfTemperature,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import WafeConfigEntry
from .entity import WafeEntity

PARALLEL_UPDATES = 0

STATE_OPTIONS = [state.name.lower() for state in UnitState if state]


@dataclass(frozen=True, kw_only=True)
class WafeSensorEntityDescription(SensorEntityDescription):
    """Describe a WAFE sensor."""

    value_fn: Callable[[WafeUnit], float | int | str | None]


def _temperature(
    key: str, value_fn: Callable[[WafeUnit], float | None]
) -> WafeSensorEntityDescription:
    return WafeSensorEntityDescription(
        key=key,
        translation_key=key,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        value_fn=value_fn,
    )


def _state(device: WafeUnit) -> str | None:
    state = device.status.state
    return state.name.lower() if state else None


SENSOR_DESCRIPTIONS: tuple[WafeSensorEntityDescription, ...] = (
    _temperature("outdoor_temperature", lambda d: d.status.outdoor_temperature),
    _temperature("supply_temperature", lambda d: d.status.supply_temperature),
    _temperature("extract_temperature", lambda d: d.status.extract_temperature),
    _temperature("exhaust_temperature", lambda d: d.status.exhaust_temperature),
    WafeSensorEntityDescription(
        key="co2",
        device_class=SensorDeviceClass.CO2,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfRatio.PARTS_PER_MILLION,
        value_fn=lambda d: d.status.co2,
    ),
    WafeSensorEntityDescription(
        key="target_airflow",
        translation_key="target_airflow",
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        value_fn=lambda d: d.status.target_airflow,
    ),
    WafeSensorEntityDescription(
        key="state",
        translation_key="state",
        device_class=SensorDeviceClass.ENUM,
        options=STATE_OPTIONS,
        value_fn=_state,
    ),
    WafeSensorEntityDescription(
        key="fan_1_speed",
        translation_key="fan_1_speed",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
        value_fn=lambda d: d.status.fan_1_speed,
    ),
    WafeSensorEntityDescription(
        key="fan_2_speed",
        translation_key="fan_2_speed",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
        value_fn=lambda d: d.status.fan_2_speed,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WafeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the WAFE sensors."""
    async_add_entities(
        WafeSensor(entry.runtime_data, description)
        for description in SENSOR_DESCRIPTIONS
    )


class WafeSensor(WafeEntity, SensorEntity):
    """A sensor of a WAFE unit."""

    entity_description: WafeSensorEntityDescription

    @property
    @override
    def native_value(self) -> float | int | str | None:
        """Return the value the unit reported."""
        return self.entity_description.value_fn(self.device)
