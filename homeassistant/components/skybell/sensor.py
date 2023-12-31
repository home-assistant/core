"""Sensor support for Skybell Doorbells."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from aioskybell import SkybellDevice
from aioskybell.helpers import const as CONST

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .entity import DOMAIN, SkybellEntity


@dataclass(frozen=True)
class SkybellSensorEntityDescriptionMixIn:
    """Mixin for Skybell sensor."""

    value_fn: Callable[[SkybellDevice], StateType | datetime]


@dataclass(frozen=True)
class SkybellSensorEntityDescription(
    SensorEntityDescription, SkybellSensorEntityDescriptionMixIn
):
    """Class to describe a Skybell sensor."""


SENSOR_TYPES: tuple[SkybellSensorEntityDescription, ...] = (
    SkybellSensorEntityDescription(
        key="chime_level",
        translation_key="chime_level",
        icon="mdi:bell-ring",
        value_fn=lambda device: device.outdoor_chime_level,
    ),
    SkybellSensorEntityDescription(
        key="last_button_event",
        translation_key="last_button_event",
        icon="mdi:clock",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda device: device.latest("button").get(CONST.CREATED_AT),
    ),
    SkybellSensorEntityDescription(
        key="last_motion_event",
        translation_key="last_motion_event",
        icon="mdi:clock",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda device: device.latest("motion").get(CONST.CREATED_AT),
    ),
    SkybellSensorEntityDescription(
        key=CONST.ATTR_LAST_CHECK_IN,
        translation_key="last_check_in",
        icon="mdi:clock",
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.last_check_in,
    ),
    SkybellSensorEntityDescription(
        key="motion_threshold",
        translation_key="motion_threshold",
        icon="mdi:walk",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.motion_threshold,
    ),
    SkybellSensorEntityDescription(
        key="video_profile",
        translation_key="video_profile",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.video_profile,
    ),
    SkybellSensorEntityDescription(
        key=CONST.ATTR_WIFI_SSID,
        translation_key="wifi_ssid",
        icon="mdi:wifi-settings",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.wifi_ssid,
    ),
    SkybellSensorEntityDescription(
        key=CONST.ATTR_WIFI_STATUS,
        translation_key="wifi_status",
        icon="mdi:wifi-strength-3",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.wifi_status,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Skybell sensor."""
    async_add_entities(
        SkybellSensor(coordinator, description)
        for coordinator in hass.data[DOMAIN][entry.entry_id]
        for description in SENSOR_TYPES
        if coordinator.device.owner or description.key not in CONST.ATTR_OWNER_STATS
    )


class SkybellSensor(SkybellEntity, SensorEntity):
    """A sensor implementation for Skybell devices."""

    entity_description: SkybellSensorEntityDescription

    @property
    def native_value(self) -> StateType | datetime:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self._device)
