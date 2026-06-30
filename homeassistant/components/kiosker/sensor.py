"""Sensor platform for Kiosker."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import KioskerConfigEntry
from .coordinator import KioskerData
from .entity import KioskerEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class KioskerSensorEntityDescription(SensorEntityDescription):
    """Kiosker sensor description."""

    value_fn: Callable[[KioskerData], StateType | datetime | None]


SENSORS: tuple[KioskerSensorEntityDescription, ...] = (
    KioskerSensorEntityDescription(
        key="batteryLevel",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda x: x.status.battery_level,
    ),
    KioskerSensorEntityDescription(
        key="lastInteraction",
        translation_key="last_interaction",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda x: x.status.last_interaction,
    ),
    KioskerSensorEntityDescription(
        key="lastMotion",
        translation_key="last_motion",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda x: x.status.last_motion,
    ),
    KioskerSensorEntityDescription(
        key="ambientLight",
        translation_key="ambient_light",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda x: x.status.ambient_light,
    ),
    KioskerSensorEntityDescription(
        key="blackoutText",
        translation_key="blackout_text",
        entity_registry_enabled_default=False,
        value_fn=lambda x: x.blackout.text if x.blackout else None,
    ),
    KioskerSensorEntityDescription(
        key="blackoutIcon",
        translation_key="blackout_icon",
        entity_registry_enabled_default=False,
        value_fn=lambda x: x.blackout.icon if x.blackout else None,
    ),
    KioskerSensorEntityDescription(
        key="blackoutBackground",
        translation_key="blackout_background",
        entity_registry_enabled_default=False,
        value_fn=lambda x: x.blackout.background if x.blackout else None,
    ),
    KioskerSensorEntityDescription(
        key="blackoutForeground",
        translation_key="blackout_foreground",
        entity_registry_enabled_default=False,
        value_fn=lambda x: x.blackout.foreground if x.blackout else None,
    ),
    KioskerSensorEntityDescription(
        key="blackoutExpire",
        translation_key="blackout_expire",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_registry_enabled_default=False,
        value_fn=lambda x: (
            x.status.last_update + timedelta(seconds=x.blackout.expire)
            if x.blackout and x.blackout.expire is not None
            else None
        ),
    ),
    KioskerSensorEntityDescription(
        key="blackoutButtonBackground",
        translation_key="blackout_button_background",
        entity_registry_enabled_default=False,
        value_fn=lambda x: x.blackout.buttonBackground if x.blackout else None,
    ),
    KioskerSensorEntityDescription(
        key="blackoutButtonForeground",
        translation_key="blackout_button_foreground",
        entity_registry_enabled_default=False,
        value_fn=lambda x: x.blackout.buttonForeground if x.blackout else None,
    ),
    KioskerSensorEntityDescription(
        key="blackoutButtonText",
        translation_key="blackout_button_text",
        entity_registry_enabled_default=False,
        value_fn=lambda x: x.blackout.buttonText if x.blackout else None,
    ),
    KioskerSensorEntityDescription(
        key="blackoutSound",
        translation_key="blackout_sound",
        entity_registry_enabled_default=False,
        value_fn=lambda x: x.blackout.sound if x.blackout else None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KioskerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Kiosker sensors based on a config entry."""
    coordinator = entry.runtime_data

    async_add_entities(
        KioskerSensor(coordinator, description) for description in SENSORS
    )


class KioskerSensor(KioskerEntity, SensorEntity):
    """Representation of a Kiosker sensor."""

    entity_description: KioskerSensorEntityDescription

    @property
    @override
    def native_value(self) -> StateType | datetime | None:
        """Return the native value of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
