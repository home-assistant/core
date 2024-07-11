"""Support for Hue binary sensors."""

from __future__ import annotations

from functools import partial

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
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from ..bridge import HueBridge
from ..const import DOMAIN
from .entity import HueBaseEntity

type SensorType = CameraMotion | Contact | Motion | EntertainmentConfiguration | Tamper
type ControllerType = (
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
        make_binary_sensor_entity = partial(sensor_class, bridge, controller)

        @callback
        def async_add_sensor(event_type: EventType, resource: SensorType) -> None:
            """Add Hue Binary Sensor."""
            async_add_entities([make_binary_sensor_entity(resource)])

        # add all current items in controller
        async_add_entities(make_binary_sensor_entity(sensor) for sensor in controller)

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


class HueMotionSensor(HueBaseEntity, BinarySensorEntity):
    """Representation of a Hue Motion sensor."""

    controller: CameraMotionController | MotionController
    resource: CameraMotion | Motion

    entity_description = BinarySensorEntityDescription(
        key="motion_sensor",
        device_class=BinarySensorDeviceClass.MOTION,
        has_entity_name=True,
    )

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        if not self.resource.enabled:
            # Force None (unknown) if the sensor is set to disabled in Hue
            return None
        return self.resource.motion.value


class HueEntertainmentActiveSensor(HueBaseEntity, BinarySensorEntity):
    """Representation of a Hue Entertainment Configuration as binary sensor."""

    controller: EntertainmentConfigurationController
    resource: EntertainmentConfiguration

    entity_description = BinarySensorEntityDescription(
        key="entertainment_active_sensor",
        device_class=BinarySensorDeviceClass.RUNNING,
        has_entity_name=False,
    )

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        return self.resource.status == EntertainmentStatus.ACTIVE

    @property
    def name(self) -> str:
        """Return sensor name."""
        return self.resource.metadata.name


class HueContactSensor(HueBaseEntity, BinarySensorEntity):
    """Representation of a Hue Contact sensor."""

    controller: ContactController
    resource: Contact

    entity_description = BinarySensorEntityDescription(
        key="contact_sensor",
        device_class=BinarySensorDeviceClass.OPENING,
        has_entity_name=True,
    )

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        if not self.resource.enabled:
            # Force None (unknown) if the sensor is set to disabled in Hue
            return None
        return self.resource.contact_report.state != ContactState.CONTACT


class HueTamperSensor(HueBaseEntity, BinarySensorEntity):
    """Representation of a Hue Tamper sensor."""

    controller: TamperController
    resource: Tamper

    entity_description = BinarySensorEntityDescription(
        key="tamper_sensor",
        device_class=BinarySensorDeviceClass.TAMPER,
        entity_category=EntityCategory.DIAGNOSTIC,
        has_entity_name=True,
    )

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        if not self.resource.tamper_reports:
            return False
        return self.resource.tamper_reports[0].state == TamperState.TAMPERED
