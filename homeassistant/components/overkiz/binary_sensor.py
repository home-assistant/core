"""Support for Overkiz binary sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from pyoverkiz.enums import OverkizCommandParam, OverkizState

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HomeAssistantOverkizData
from .const import DOMAIN, IGNORED_OVERKIZ_DEVICES
from .entity import OverkizDescriptiveEntity


@dataclass
class OverkizBinarySensorDescriptionMixin:
    """Define an entity description mixin for binary sensor entities."""

    is_on: Callable[[str], bool]


@dataclass
class OverkizBinarySensorDescription(
    BinarySensorEntityDescription, OverkizBinarySensorDescriptionMixin
):
    """Class to describe an Overkiz binary sensor."""


BINARY_SENSOR_DESCRIPTIONS: list[OverkizBinarySensorDescription] = [
    # RainSensor/RainSensor
    OverkizBinarySensorDescription(
        key=OverkizState.CORE_RAIN,
        name="Rain",
        icon="mdi:weather-rainy",
        is_on=lambda state: state == OverkizCommandParam.DETECTED,
    ),
    # SmokeSensor/SmokeSensor
    OverkizBinarySensorDescription(
        key=OverkizState.CORE_SMOKE,
        name="Smoke",
        device_class=BinarySensorDeviceClass.SMOKE,
        is_on=lambda state: state == OverkizCommandParam.DETECTED,
    ),
    # WaterSensor/WaterDetectionSensor
    OverkizBinarySensorDescription(
        key=OverkizState.CORE_WATER_DETECTION,
        name="Water",
        icon="mdi:water",
        is_on=lambda state: state == OverkizCommandParam.DETECTED,
    ),
    # AirSensor/AirFlowSensor
    OverkizBinarySensorDescription(
        key=OverkizState.CORE_GAS_DETECTION,
        name="Gas",
        device_class=BinarySensorDeviceClass.GAS,
        is_on=lambda state: state == OverkizCommandParam.DETECTED,
    ),
    # OccupancySensor/OccupancySensor
    # OccupancySensor/MotionSensor
    OverkizBinarySensorDescription(
        key=OverkizState.CORE_OCCUPANCY,
        name="Occupancy",
        device_class=BinarySensorDeviceClass.OCCUPANCY,
        is_on=lambda state: state == OverkizCommandParam.PERSON_INSIDE,
    ),
    # ContactSensor/WindowWithTiltSensor
    OverkizBinarySensorDescription(
        key=OverkizState.CORE_VIBRATION,
        name="Vibration",
        device_class=BinarySensorDeviceClass.VIBRATION,
        is_on=lambda state: state == OverkizCommandParam.DETECTED,
    ),
    # ContactSensor/ContactSensor
    OverkizBinarySensorDescription(
        key=OverkizState.CORE_CONTACT,
        name="Contact",
        device_class=BinarySensorDeviceClass.DOOR,
        is_on=lambda state: state == OverkizCommandParam.OPEN,
    ),
    # Siren/SirenStatus
    OverkizBinarySensorDescription(
        key=OverkizState.CORE_ASSEMBLY,
        name="Assembly",
        device_class=BinarySensorDeviceClass.PROBLEM,
        is_on=lambda state: state == OverkizCommandParam.OPEN,
    ),
    # Unknown
    OverkizBinarySensorDescription(
        key=OverkizState.IO_VIBRATION_DETECTED,
        name="Vibration",
        device_class=BinarySensorDeviceClass.VIBRATION,
        is_on=lambda state: state == OverkizCommandParam.DETECTED,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    """Set up the Overkiz binary sensors from a config entry."""
    data: HomeAssistantOverkizData = hass.data[DOMAIN][entry.entry_id]
    entities: list[OverkizBinarySensor] = []

    key_supported_states = {
        description.key: description for description in BINARY_SENSOR_DESCRIPTIONS
    }

    for device in data.coordinator.data.values():
        if (
            device.widget in IGNORED_OVERKIZ_DEVICES
            or device.ui_class in IGNORED_OVERKIZ_DEVICES
        ):
            continue

        for state in device.definition.states:
            if description := key_supported_states.get(state.qualified_name):
                entities.append(
                    OverkizBinarySensor(
                        device.device_url,
                        data.coordinator,
                        description,
                    )
                )

    async_add_entities(entities)


class OverkizBinarySensor(OverkizDescriptiveEntity, BinarySensorEntity):
    """Representation of an Overkiz Binary Sensor."""

    entity_description: OverkizBinarySensorDescription

    @property
    def is_on(self) -> bool | None:
        """Return the state of the sensor."""
        state = self.device.states.get(self.entity_description.key)

        if not state:
            return None

        return self.entity_description.is_on(state.value)
