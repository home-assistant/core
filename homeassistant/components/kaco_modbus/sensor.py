"""What the inverter measures."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from kaco_modbus.models import InverterThreePhase

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import KacoConfigEntry
from .entity import KacoEntity, KacoEntityDescription

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class KacoSensorDescription(SensorEntityDescription, KacoEntityDescription):
    """A sensor, and where to read its value off the inverter block."""

    value_fn: Callable[[InverterThreePhase], StateType]


SENSOR_DESCRIPTIONS: tuple[KacoSensorDescription, ...] = (
    KacoSensorDescription(
        key="ac_power",
        component="inverter",
        translation_key="ac_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda inverter: inverter.w,
    ),
    KacoSensorDescription(
        key="lifetime_energy",
        component="inverter",
        translation_key="lifetime_energy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=2,
        value_fn=lambda inverter: inverter.wh,
    ),
    KacoSensorDescription(
        key="operating_state",
        component="inverter",
        translation_key="operating_state",
        device_class=SensorDeviceClass.ENUM,
        options=[
            "off",
            "sleeping",
            "starting",
            "mppt",
            "throttled",
            "shutting_down",
            "fault",
            "standby",
        ],
        value_fn=lambda inverter: (
            None if inverter.st is None else inverter.st.name.lower()
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KacoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the KACO Modbus sensor platform."""
    async_add_entities(
        KacoSensor(entry.runtime_data, description)
        for description in SENSOR_DESCRIPTIONS
    )


class KacoSensor(KacoEntity, SensorEntity):
    """A read-only value off one of the inverter's components."""

    entity_description: KacoSensorDescription

    @property
    @override
    def native_value(self) -> StateType:
        """Return the value this sensor reads from the device."""
        component = getattr(self.coordinator.device, self.entity_description.component)
        return self.entity_description.value_fn(component)
