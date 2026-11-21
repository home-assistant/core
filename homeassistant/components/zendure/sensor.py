"""Sensor platform for Zendure devices."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from zendure import PropertyValue

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import ZendureConfigEntry
from .entity import ZendureEntity

PARALLEL_UPDATES = 0


# Raw state codes reported by packState.
PACK_STATES = {0: "standby", 1: "charging", 2: "discharging"}


def _pack_state(value: PropertyValue) -> str | None:
    """Map a raw pack state code to its option, or unknown."""
    if not isinstance(value, int):
        return None
    return PACK_STATES.get(value)


@dataclass(frozen=True, kw_only=True)
class ZendureSensorEntityDescription(SensorEntityDescription):
    """Describes a Zendure sensor entity."""

    value_fn: Callable[[PropertyValue], StateType] = lambda value: value


def _power(key: str, translation_key: str) -> ZendureSensorEntityDescription:
    """Describe an instantaneous power sensor."""
    return ZendureSensorEntityDescription(
        key=key,
        translation_key=translation_key,
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
    )


DEVICE_SENSORS: tuple[ZendureSensorEntityDescription, ...] = (
    ZendureSensorEntityDescription(
        key="electricLevel",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    _power("solarInputPower", "solar_input_power"),
    _power("solarPower1", "solar_power_1"),
    _power("solarPower2", "solar_power_2"),
    _power("solarPower3", "solar_power_3"),
    _power("solarPower4", "solar_power_4"),
    _power("outputHomePower", "output_home_power"),
    _power("gridInputPower", "grid_input_power"),
    _power("gridOffPower", "grid_off_power"),
    _power("outputPackPower", "battery_charge_power"),
    _power("packInputPower", "battery_discharge_power"),
    ZendureSensorEntityDescription(
        key="remainOutTime",
        translation_key="remaining_discharge_time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ZendureSensorEntityDescription(
        key="packState",
        translation_key="pack_state",
        device_class=SensorDeviceClass.ENUM,
        options=list(PACK_STATES.values()),
        value_fn=_pack_state,
    ),
    ZendureSensorEntityDescription(
        key="hyperTmp",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ZendureSensorEntityDescription(
        key="packNum",
        translation_key="pack_count",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ZendureSensorEntityDescription(
        key="inverseMaxPower",
        translation_key="max_output_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ZendureSensorEntityDescription(
        key="chargeMaxLimit",
        translation_key="max_charge_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ZendureSensorEntityDescription(
        key="rssi",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ZendureConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Zendure sensors based on a config entry."""
    coordinator = entry.runtime_data
    reported = coordinator.data.properties
    async_add_entities(
        ZendureSensorEntity(coordinator, description)
        for description in DEVICE_SENSORS
        if description.key in reported
    )


class ZendureSensorEntity(ZendureEntity, SensorEntity):
    """A sensor of the Zendure device."""

    entity_description: ZendureSensorEntityDescription

    @property
    @override
    def native_value(self) -> StateType:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.raw_value)
