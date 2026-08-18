"""Support for Overkiz binary sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import cast, override

from pyoverkiz.enums import OverkizCommandParam, OverkizState, UIClass, UIWidget
from pyoverkiz.types import StateType as OverkizStateType

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import OverkizDataConfigEntry
from .const import IGNORED_OVERKIZ_DEVICES
from .entity import OverkizDescriptiveEntity


@dataclass(frozen=True, kw_only=True)
class OverkizBinarySensorDescription(BinarySensorEntityDescription):
    """Class to describe an Overkiz binary sensor."""

    value_fn: Callable[[OverkizStateType], bool]

    # Restrict this entity to the listed device types (UIWidget/UIClass).
    # When omitted, the sensor applies to any device exposing the state.
    device_types: list[UIWidget | UIClass] | None = None


BINARY_SENSOR_DESCRIPTIONS: list[OverkizBinarySensorDescription] = [
    # RainSensor/RainSensor
    OverkizBinarySensorDescription(
        key=OverkizState.CORE_RAIN,
        name="Rain",
        icon="mdi:weather-rainy",
        value_fn=lambda state: state == OverkizCommandParam.DETECTED,
    ),
    # SmokeSensor/SmokeSensor
    OverkizBinarySensorDescription(
        key=OverkizState.CORE_SMOKE,
        name="Smoke",
        device_class=BinarySensorDeviceClass.SMOKE,
        value_fn=lambda state: state == OverkizCommandParam.DETECTED,
    ),
    # WaterSensor/WaterDetectionSensor
    OverkizBinarySensorDescription(
        key=OverkizState.CORE_WATER_DETECTION,
        name="Water",
        icon="mdi:water",
        device_class=BinarySensorDeviceClass.MOISTURE,
        value_fn=lambda state: state == OverkizCommandParam.DETECTED,
    ),
    # AirSensor/AirFlowSensor
    OverkizBinarySensorDescription(
        key=OverkizState.CORE_GAS_DETECTION,
        name="Gas",
        device_class=BinarySensorDeviceClass.GAS,
        value_fn=lambda state: state == OverkizCommandParam.DETECTED,
    ),
    # OccupancySensor/OccupancySensor
    # OccupancySensor/MotionSensor
    OverkizBinarySensorDescription(
        key=OverkizState.CORE_OCCUPANCY,
        name="Occupancy",
        device_class=BinarySensorDeviceClass.OCCUPANCY,
        value_fn=lambda state: state == OverkizCommandParam.PERSON_INSIDE,
    ),
    # ContactSensor/WindowWithTiltSensor
    OverkizBinarySensorDescription(
        key=OverkizState.CORE_VIBRATION,
        name="Vibration",
        device_class=BinarySensorDeviceClass.VIBRATION,
        value_fn=lambda state: state == OverkizCommandParam.DETECTED,
    ),
    # ContactSensor/ContactSensor
    OverkizBinarySensorDescription(
        key=OverkizState.CORE_CONTACT,
        name="Contact",
        device_class=BinarySensorDeviceClass.DOOR,
        value_fn=lambda state: state == OverkizCommandParam.OPEN,
    ),
    # Siren/SirenStatus
    OverkizBinarySensorDescription(
        key=OverkizState.CORE_ASSEMBLY,
        name="Assembly",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda state: state == OverkizCommandParam.OPEN,
    ),
    # Unknown
    OverkizBinarySensorDescription(
        key=OverkizState.IO_VIBRATION_DETECTED,
        name="Vibration",
        device_class=BinarySensorDeviceClass.VIBRATION,
        value_fn=lambda state: state == OverkizCommandParam.DETECTED,
    ),
    # DomesticHotWaterProduction/WaterHeatingSystem
    OverkizBinarySensorDescription(
        key=OverkizState.IO_OPERATING_MODE_CAPABILITIES,
        name="Energy demand status",
        device_class=BinarySensorDeviceClass.HEAT,
        value_fn=lambda state: (
            cast(dict, state).get(OverkizCommandParam.ENERGY_DEMAND_STATUS) == 1
        ),
    ),
    OverkizBinarySensorDescription(
        key=OverkizState.CORE_HEATING_STATUS,
        name="Heating status",
        device_class=BinarySensorDeviceClass.HEAT,
        value_fn=lambda state: (
            cast(str, state).lower()
            in (OverkizCommandParam.ON, OverkizCommandParam.HEATING)
        ),
    ),
    OverkizBinarySensorDescription(
        key=OverkizState.MODBUSLINK_DHW_ABSENCE_MODE,
        name="Absence mode",
        value_fn=(
            lambda state: state in (OverkizCommandParam.ON, OverkizCommandParam.PROG)
        ),
    ),
    OverkizBinarySensorDescription(
        key=OverkizState.MODBUSLINK_DHW_BOOST_MODE,
        name="Boost mode",
        value_fn=(
            lambda state: state in (OverkizCommandParam.ON, OverkizCommandParam.PROG)
        ),
    ),
    OverkizBinarySensorDescription(
        key=OverkizState.MODBUSLINK_DHW_MODE,
        name="Manual mode",
        value_fn=(
            lambda state: (
                state
                in (OverkizCommandParam.MANUAL, OverkizCommandParam.MANUAL_ECO_INACTIVE)
            )
        ),
    ),
    # ContactSensor/IntrusionEventSensor
    # (io:SomfyWindowStateSensor, io:SomfySlidingWindowStateSensor)
    OverkizBinarySensorDescription(
        key=OverkizState.CORE_OPEN_CLOSED,
        device_class=BinarySensorDeviceClass.WINDOW,
        value_fn=lambda state: state == OverkizCommandParam.OPEN,
        # core:OpenClosedState is also exposed by all cover devices,
        # restrict this to ContactSensor devices (e.g. the Somfy IntelliTAG)
        device_types=[UIClass.CONTACT_SENSOR],
    ),
    # ContactSensor/IntrusionEventSensor (io:SomfyWindowStateSensor)
    OverkizBinarySensorDescription(
        key=OverkizState.CORE_TILTED,
        name="Tilt",
        icon="mdi:angle-acute",
        value_fn=bool,
    ),
]

SUPPORTED_STATES = {
    description.key: description for description in BINARY_SENSOR_DESCRIPTIONS
}


PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OverkizDataConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Overkiz binary sensors from a config entry."""
    data = entry.runtime_data
    entities: list[OverkizBinarySensor] = []

    for device in data.coordinator.data.values():
        if (
            device.widget in IGNORED_OVERKIZ_DEVICES
            or device.ui_class in IGNORED_OVERKIZ_DEVICES
        ):
            continue

        entities.extend(
            OverkizBinarySensor(
                device.device_url,
                data.coordinator,
                description,
            )
            for state in device.definition.states
            if (description := SUPPORTED_STATES.get(state))
            and (
                description.device_types is None
                or device.widget in description.device_types
                or device.ui_class in description.device_types
            )
        )

    async_add_entities(entities)


class OverkizBinarySensor(OverkizDescriptiveEntity, BinarySensorEntity):
    """Representation of an Overkiz Binary Sensor."""

    entity_description: OverkizBinarySensorDescription

    @property
    @override
    def is_on(self) -> bool | None:
        """Return the state of the sensor."""
        if state := self.device.states.get(self.entity_description.key):
            return self.entity_description.value_fn(state.value)

        return None
