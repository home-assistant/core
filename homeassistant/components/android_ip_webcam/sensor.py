"""Support for Android IP Webcam sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from pydroid_ipcam import PyDroidIPCam

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import DOMAIN
from .coordinator import AndroidIPCamDataUpdateCoordinator
from .entity import AndroidIPCamBaseEntity


@dataclass
class AndroidIPWebcamSensorEntityDescriptionMixin:
    """Mixin for required keys."""

    value_fn: Callable[[PyDroidIPCam], StateType]


@dataclass
class AndroidIPWebcamSensorEntityDescription(
    SensorEntityDescription, AndroidIPWebcamSensorEntityDescriptionMixin
):
    """Entity description class for Android IP Webcam sensors."""

    unit_fn: Callable[[PyDroidIPCam], str | None] = lambda _: None


SENSOR_TYPES: tuple[AndroidIPWebcamSensorEntityDescription, ...] = (
    AndroidIPWebcamSensorEntityDescription(
        key="audio_connections",
        name="Audio connections",
        icon="mdi:speaker",
        state_class=SensorStateClass.TOTAL,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda ipcam: ipcam.status_data.get("audio_connections"),
    ),
    AndroidIPWebcamSensorEntityDescription(
        key="battery_level",
        name="Battery level",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda ipcam: ipcam.export_sensor("battery_level")[0],
        unit_fn=lambda ipcam: ipcam.export_sensor("battery_level")[1],
    ),
    AndroidIPWebcamSensorEntityDescription(
        key="battery_temp",
        name="Battery temperature",
        icon="mdi:thermometer",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda ipcam: ipcam.export_sensor("battery_temp")[0],
        unit_fn=lambda ipcam: ipcam.export_sensor("battery_temp")[1],
    ),
    AndroidIPWebcamSensorEntityDescription(
        key="battery_voltage",
        name="Battery voltage",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda ipcam: ipcam.export_sensor("battery_voltage")[0],
        unit_fn=lambda ipcam: ipcam.export_sensor("battery_voltage")[1],
    ),
    AndroidIPWebcamSensorEntityDescription(
        key="light",
        name="Light level",
        icon="mdi:flashlight",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda ipcam: ipcam.export_sensor("light")[0],
        unit_fn=lambda ipcam: ipcam.export_sensor("light")[1],
    ),
    AndroidIPWebcamSensorEntityDescription(
        key="motion",
        name="Motion",
        icon="mdi:run",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda ipcam: ipcam.export_sensor("motion")[0],
        unit_fn=lambda ipcam: ipcam.export_sensor("motion")[1],
    ),
    AndroidIPWebcamSensorEntityDescription(
        key="pressure",
        name="Pressure",
        icon="mdi:gauge",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda ipcam: ipcam.export_sensor("pressure")[0],
        unit_fn=lambda ipcam: ipcam.export_sensor("pressure")[1],
    ),
    AndroidIPWebcamSensorEntityDescription(
        key="proximity",
        name="Proximity",
        icon="mdi:map-marker-radius",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda ipcam: ipcam.export_sensor("proximity")[0],
        unit_fn=lambda ipcam: ipcam.export_sensor("proximity")[1],
    ),
    AndroidIPWebcamSensorEntityDescription(
        key="sound",
        name="Sound",
        icon="mdi:speaker",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda ipcam: ipcam.export_sensor("sound")[0],
        unit_fn=lambda ipcam: ipcam.export_sensor("sound")[1],
    ),
    AndroidIPWebcamSensorEntityDescription(
        key="video_connections",
        name="Video connections",
        icon="mdi:eye",
        state_class=SensorStateClass.TOTAL,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda ipcam: ipcam.status_data.get("video_connections"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the IP Webcam sensors from config entry."""

    coordinator: AndroidIPCamDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]
    sensor_types = [
        sensor
        for sensor in SENSOR_TYPES
        if sensor.key
        in coordinator.cam.enabled_sensors + ["audio_connections", "video_connections"]
    ]
    async_add_entities(
        IPWebcamSensor(coordinator, description) for description in sensor_types
    )


class IPWebcamSensor(AndroidIPCamBaseEntity, SensorEntity):
    """Representation of a IP Webcam sensor."""

    entity_description: AndroidIPWebcamSensorEntityDescription

    def __init__(
        self,
        coordinator: AndroidIPCamDataUpdateCoordinator,
        description: AndroidIPWebcamSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}-{description.key}"
        self.entity_description = description
        super().__init__(coordinator)

    @property
    def native_value(self) -> StateType:
        """Return native value of sensor."""
        return self.entity_description.value_fn(self.cam)

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return native unit of measurement of sensor."""
        return self.entity_description.unit_fn(self.cam)
