"""Sensor platform for Sun integration."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from homeassistant.components.sensor import (
    DOMAIN as SENSOR_DOMAIN,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import DEGREE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import Sun
from .const import DOMAIN

ENTITY_ID_SENSOR_FORMAT = SENSOR_DOMAIN + ".sun_{}"


@dataclass
class SunEntityDescriptionMixin:
    """Mixin for required Sun base description keys."""

    value_fn: Callable[[Sun], StateType | datetime]


@dataclass
class SunSensorEntityDescription(SensorEntityDescription, SunEntityDescriptionMixin):
    """Describes Sun sensor entity."""


SENSOR_TYPES: tuple[SunSensorEntityDescription, ...] = (
    SunSensorEntityDescription(
        key="next_dawn",
        device_class=SensorDeviceClass.TIMESTAMP,
        translation_key="next_dawn",
        icon="mdi:sun-clock",
        value_fn=lambda data: data.next_dawn,
    ),
    SunSensorEntityDescription(
        key="next_dusk",
        device_class=SensorDeviceClass.TIMESTAMP,
        translation_key="next_dusk",
        icon="mdi:sun-clock",
        value_fn=lambda data: data.next_dusk,
    ),
    SunSensorEntityDescription(
        key="next_midnight",
        device_class=SensorDeviceClass.TIMESTAMP,
        translation_key="next_midnight",
        icon="mdi:sun-clock",
        value_fn=lambda data: data.next_midnight,
    ),
    SunSensorEntityDescription(
        key="next_noon",
        device_class=SensorDeviceClass.TIMESTAMP,
        translation_key="next_noon",
        icon="mdi:sun-clock",
        value_fn=lambda data: data.next_noon,
    ),
    SunSensorEntityDescription(
        key="next_rising",
        device_class=SensorDeviceClass.TIMESTAMP,
        translation_key="next_rising",
        icon="mdi:sun-clock",
        value_fn=lambda data: data.next_rising,
    ),
    SunSensorEntityDescription(
        key="next_setting",
        device_class=SensorDeviceClass.TIMESTAMP,
        translation_key="next_setting",
        icon="mdi:sun-clock",
        value_fn=lambda data: data.next_setting,
    ),
    SunSensorEntityDescription(
        key="solar_elevation",
        translation_key="solar_elevation",
        icon="mdi:theme-light-dark",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.solar_elevation,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=DEGREE,
    ),
    SunSensorEntityDescription(
        key="solar_azimuth",
        translation_key="solar_azimuth",
        icon="mdi:sun-angle",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.solar_azimuth,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=DEGREE,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Sun sensor platform."""

    sun: Sun = hass.data[DOMAIN]

    async_add_entities(
        [SunSensor(sun, description, entry.entry_id) for description in SENSOR_TYPES]
    )


class SunSensor(SensorEntity):
    """Representation of a Sun Sensor."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    entity_description: SunSensorEntityDescription

    def __init__(
        self, sun: Sun, entity_description: SunSensorEntityDescription, entry_id: str
    ) -> None:
        """Initiate Sun Sensor."""
        self.entity_description = entity_description
        self.entity_id = ENTITY_ID_SENSOR_FORMAT.format(entity_description.key)
        self._attr_unique_id = f"{entry_id}-{entity_description.key}"
        self.sun = sun

        self._attr_device_info = DeviceInfo(
            name="Sun",
            identifiers={(DOMAIN, entry_id)},
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def native_value(self) -> StateType | datetime:
        """Return value of sensor."""
        state = self.entity_description.value_fn(self.sun)
        return state
