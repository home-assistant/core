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
from homeassistant.const import DEGREE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import DOMAIN, SIGNAL_EVENTS_CHANGED, SIGNAL_POSITION_CHANGED
from .entity import Sun, SunConfigEntry

ENTITY_ID_SENSOR_FORMAT = SENSOR_DOMAIN + ".sun_{}"


@dataclass(kw_only=True, frozen=True)
class SunSensorEntityDescription(SensorEntityDescription):
    """Describes a Sun sensor entity."""

    value_fn: Callable[[Sun], StateType | datetime]
    signal: str


SENSOR_TYPES: tuple[SunSensorEntityDescription, ...] = (
    SunSensorEntityDescription(
        key="next_dawn",
        device_class=SensorDeviceClass.TIMESTAMP,
        translation_key="next_dawn",
        value_fn=lambda data: data.next_dawn,
        signal=SIGNAL_EVENTS_CHANGED,
    ),
    SunSensorEntityDescription(
        key="next_dusk",
        device_class=SensorDeviceClass.TIMESTAMP,
        translation_key="next_dusk",
        value_fn=lambda data: data.next_dusk,
        signal=SIGNAL_EVENTS_CHANGED,
    ),
    SunSensorEntityDescription(
        key="next_midnight",
        device_class=SensorDeviceClass.TIMESTAMP,
        translation_key="next_midnight",
        value_fn=lambda data: data.next_midnight,
        signal=SIGNAL_EVENTS_CHANGED,
    ),
    SunSensorEntityDescription(
        key="next_noon",
        device_class=SensorDeviceClass.TIMESTAMP,
        translation_key="next_noon",
        value_fn=lambda data: data.next_noon,
        signal=SIGNAL_EVENTS_CHANGED,
    ),
    SunSensorEntityDescription(
        key="next_rising",
        device_class=SensorDeviceClass.TIMESTAMP,
        translation_key="next_rising",
        value_fn=lambda data: data.next_rising,
        signal=SIGNAL_EVENTS_CHANGED,
    ),
    SunSensorEntityDescription(
        key="next_setting",
        device_class=SensorDeviceClass.TIMESTAMP,
        translation_key="next_setting",
        value_fn=lambda data: data.next_setting,
        signal=SIGNAL_EVENTS_CHANGED,
    ),
    SunSensorEntityDescription(
        key="solar_elevation",
        translation_key="solar_elevation",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.solar_elevation,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=DEGREE,
        signal=SIGNAL_POSITION_CHANGED,
    ),
    SunSensorEntityDescription(
        key="solar_azimuth",
        translation_key="solar_azimuth",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.solar_azimuth,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=DEGREE,
        signal=SIGNAL_POSITION_CHANGED,
    ),
    SunSensorEntityDescription(
        key="solar_rising",
        translation_key="solar_rising",
        value_fn=lambda data: data.rising,
        entity_registry_enabled_default=False,
        signal=SIGNAL_EVENTS_CHANGED,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: SunConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Sun sensor platform."""

    sun = entry.runtime_data

    async_add_entities(
        [SunSensor(sun, description, entry.entry_id) for description in SENSOR_TYPES]
    )


class SunSensor(SensorEntity):
    """Representation of a Sun Sensor."""

    _attr_has_entity_name = True
    _attr_should_poll = False
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
        return self.entity_description.value_fn(self.sun)

    async def async_added_to_hass(self) -> None:
        """Register signal listener when added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                self.entity_description.signal,
                self.async_write_ha_state,
            )
        )
