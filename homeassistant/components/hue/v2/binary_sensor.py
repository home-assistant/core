"""Support for Hue binary sensors."""
from __future__ import annotations

from typing import TypeAlias

from aiohue.v2 import HueBridgeV2
from aiohue.v2.controllers.config import (
    EntertainmentConfiguration,
    EntertainmentConfigurationController,
)
from aiohue.v2.controllers.events import EventType
from aiohue.v2.controllers.sensors import (
    CameraMotionController,
    ContactController,
    MotionController,
    TamperController,
)
from aiohue.v2.models.camera_motion import CameraMotion
from aiohue.v2.models.contact import Contact, ContactState
from aiohue.v2.models.entertainment_configuration import EntertainmentStatus
from aiohue.v2.models.motion import Motion
from aiohue.v2.models.tamper import Tamper, TamperState

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from ..bridge import HueBridge
from ..const import DOMAIN
from .entity import HueBaseEntity

SensorType: TypeAlias = (
    CameraMotion | Contact | Motion | EntertainmentConfiguration | Tamper
)
ControllerType: TypeAlias = (
    CameraMotionController
    | ContactController
    | MotionController
    | EntertainmentConfigurationController
    | TamperController
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Hue Sensors from Config Entry."""
    bridge: HueBridge = hass.data[DOMAIN][config_entry.entry_id]
    api: HueBridgeV2 = bridge.api

    @callback
    def register_items(controller: ControllerType, sensor_class: SensorType):
        @callback
        def async_add_sensor(event_type: EventType, resource: SensorType) -> None:
            """Add Hue Binary Sensor."""
            async_add_entities([sensor_class(bridge, controller, resource)])

        # add all current items in controller
        for sensor in controller:
            async_add_sensor(EventType.RESOURCE_ADDED, sensor)

        # register listener for new sensors
        config_entry.async_on_unload(
            controller.subscribe(
                async_add_sensor, event_filter=EventType.RESOURCE_ADDED
            )
        )

    # setup for each binary-sensor-type hue resource
    register_items(api.sensors.camera_motion, HueMotionSensor)
    register_items(api.sensors.motion, HueMotionSensor)
    register_items(api.config.entertainment_configuration, HueEntertainmentActiveSensor)
    register_items(api.sensors.contact, HueContactSensor)
    register_items(api.sensors.tamper, HueTamperSensor)


class HueBinarySensorBase(HueBaseEntity, BinarySensorEntity):
    """Representation of a Hue binary_sensor."""

    def __init__(
        self,
        bridge: HueBridge,
        controller: ControllerType,
        resource: SensorType,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(bridge, controller, resource)
        self.resource = resource
        self.controller = controller


class HueMotionSensor(HueBinarySensorBase):
    """Representation of a Hue Motion sensor."""

    _attr_device_class = BinarySensorDeviceClass.MOTION

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        if not self.resource.enabled:
            # Force None (unknown) if the sensor is set to disabled in Hue
            return None
        return self.resource.motion.value


class HueEntertainmentActiveSensor(HueBinarySensorBase):
    """Representation of a Hue Entertainment Configuration as binary sensor."""

    _attr_device_class = BinarySensorDeviceClass.RUNNING

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        return self.resource.status == EntertainmentStatus.ACTIVE

    @property
    def name(self) -> str:
        """Return sensor name."""
        type_title = self.resource.type.value.replace("_", " ").title()
        return f"{self.resource.metadata.name}: {type_title}"


class HueContactSensor(HueBinarySensorBase):
    """Representation of a Hue Contact sensor."""

    _attr_device_class = BinarySensorDeviceClass.OPENING

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        if not self.resource.enabled:
            # Force None (unknown) if the sensor is set to disabled in Hue
            return None
        return self.resource.contact_report.state != ContactState.CONTACT


class HueTamperSensor(HueBinarySensorBase):
    """Representation of a Hue Tamper sensor."""

    _attr_device_class = BinarySensorDeviceClass.TAMPER

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        if not self.resource.tamper_reports:
            return False
        return self.resource.tamper_reports[0].state == TamperState.TAMPERED
