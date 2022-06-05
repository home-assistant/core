"""Sensor support for Skybell Doorbells."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from aioskybell import SkybellDevice
from aioskybell.helpers import const as CONST
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ENTITY_NAMESPACE, CONF_MONITORED_CONDITIONS
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import DOMAIN, SkybellEntity


@dataclass
class SkybellSensorEntityDescription(SensorEntityDescription):
    """Class to describe a Skybell sensor."""

    value_fn: Callable[[SkybellDevice], Any] = lambda val: val


SENSOR_TYPES: tuple[SkybellSensorEntityDescription, ...] = (
    SkybellSensorEntityDescription(
        key="chime_level",
        name="Chime Level",
        icon="mdi:bell-ring",
        value_fn=lambda device: device.outdoor_chime_level,
    ),
    SkybellSensorEntityDescription(
        key="last_button_event",
        name="Last Button Event",
        icon="mdi:clock",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda device: device.latest("button").get(CONST.CREATED_AT),
    ),
    SkybellSensorEntityDescription(
        key="last_motion_event",
        name="Last Motion Event",
        icon="mdi:clock",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda device: device.latest("motion").get(CONST.CREATED_AT),
    ),
    SkybellSensorEntityDescription(
        key=CONST.ATTR_LAST_CHECK_IN,
        name="Last Check in",
        icon="mdi:clock",
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.last_check_in,
    ),
    SkybellSensorEntityDescription(
        key="motion_threshold",
        name="Motion Threshold",
        icon="mdi:walk",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.motion_threshold,
    ),
    SkybellSensorEntityDescription(
        key="video_profile",
        name="Video Profile",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.video_profile,
    ),
    SkybellSensorEntityDescription(
        key=CONST.ATTR_WIFI_SSID,
        name="Wifi SSID",
        icon="mdi:wifi-settings",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.wifi_ssid,
    ),
    SkybellSensorEntityDescription(
        key=CONST.ATTR_WIFI_STATUS,
        name="Wifi Status",
        icon="mdi:wifi-strength-3",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.wifi_status,
    ),
)

MONITORED_CONDITIONS = SENSOR_TYPES

# Deprecated in Home Assistant 2022.6
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_ENTITY_NAMESPACE, default=DOMAIN): cv.string,
        vol.Required(CONF_MONITORED_CONDITIONS, default=[]): vol.All(
            cv.ensure_list, [vol.In(MONITORED_CONDITIONS)]
        ),
    }
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
    def native_value(self) -> int:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self._device)
