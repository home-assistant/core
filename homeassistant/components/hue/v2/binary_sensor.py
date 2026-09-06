"""Support for Hue binary sensors."""

from functools import partial
from typing import override

from aiohue.v2 import HueBridgeV2
from aiohue.v2.controllers.config import (
    EntertainmentConfiguration,
    EntertainmentConfigurationController,
)
from aiohue.v2.controllers.events import EventType
from aiohue.v2.controllers.sensors import (
    CameraMotionController,
    ContactController,
    GroupedMotionController,
    MotionController,
    SecurityAreaMotionController,
    TamperController,
)
from aiohue.v2.models.camera_motion import CameraMotion
from aiohue.v2.models.contact import Contact, ContactState
from aiohue.v2.models.convenience_area_motion import ConvenienceAreaMotion
from aiohue.v2.models.entertainment_configuration import EntertainmentStatus
from aiohue.v2.models.grouped_motion import GroupedMotion
from aiohue.v2.models.motion import Motion
from aiohue.v2.models.motion_area_configuration import MotionAreaHealth
from aiohue.v2.models.resource import ResourceTypes
from aiohue.v2.models.security_area_motion import SecurityAreaMotion
from aiohue.v2.models.tamper import Tamper, TamperState

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from ..bridge import HueBridge, HueConfigEntry
from ..const import DOMAIN
from .entity import HueBaseEntity

type SensorType = (
    CameraMotion
    | Contact
    | Motion
    | EntertainmentConfiguration
    | Tamper
    | GroupedMotion
    | SecurityAreaMotion
)
type ControllerType = (
    CameraMotionController
    | ContactController
    | MotionController
    | EntertainmentConfigurationController
    | TamperController
    | GroupedMotionController
    | SecurityAreaMotionController
)


def _resource_valid(resource: SensorType, controller: ControllerType) -> bool:
    """Return True if the resource is valid."""
    if isinstance(resource, GroupedMotion):
        # filter out GroupedMotion sensors that are not linked to a valid group/parent
        if resource.owner.rtype not in (
            ResourceTypes.ROOM,
            ResourceTypes.ZONE,
            ResourceTypes.SERVICE_GROUP,
        ):
            return False
        # guard against GroupedMotion without parent
        # (should not happen, but just in case)
        if not (parent := controller.get_parent(resource.id)):
            return False
        # filter out GroupedMotion sensors that have only one member,
        # because Hue creates one default grouped Motion sensor per
        # zone/room, which is not useful to expose in HA
        if len(parent.children) <= 1:
            return False
    # default/other checks can go here (none for now)
    return True


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HueConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Hue Sensors from Config Entry."""
    bridge = config_entry.runtime_data
    api: HueBridgeV2 = bridge.api

    @callback
    def register_items(controller: ControllerType, sensor_class: SensorType):
        make_binary_sensor_entity = partial(sensor_class, bridge, controller)

        @callback
        def async_add_sensor(event_type: EventType, resource: SensorType) -> None:
            """Add Hue Binary Sensor from resource added callback."""
            if not _resource_valid(resource, controller):
                return
            async_add_entities([make_binary_sensor_entity(resource)])

        # add all current items in controller
        async_add_entities(
            make_binary_sensor_entity(sensor)
            for sensor in controller
            if _resource_valid(sensor, controller)
        )

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
    register_items(api.sensors.grouped_motion, HueGroupedMotionSensor)
    register_items(api.sensors.security_area_motion, HueMotionAwareSensor)


# pylint: disable-next=home-assistant-enforce-class-module
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
    @override
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        if not self.resource.enabled:
            # Force None (unknown) if the sensor is set to disabled in Hue
            return None
        if not (motion_feature := self.resource.motion):
            return None
        if motion_feature.motion_report is not None:
            return motion_feature.motion_report.motion
        return motion_feature.motion


# pylint: disable-next=home-assistant-enforce-class-module
class HueGroupedMotionSensor(HueMotionSensor):
    """Representation of a Hue Grouped Motion sensor."""

    controller: GroupedMotionController
    resource: GroupedMotion

    def __init__(
        self,
        bridge: HueBridge,
        controller: GroupedMotionController,
        resource: GroupedMotion,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(bridge, controller, resource)
        # link the GroupedMotion sensor to the parent the sensor is associated with
        # which can either be a special ServiceGroup or a Zone/Room
        parent = self.controller.get_parent(resource.id)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, parent.id)},
        )


# pylint: disable-next=home-assistant-enforce-class-module
class HueMotionAwareSensor(HueMotionSensor):
    """Representation of a Motion sensor based on Hue Motion Aware.

    A MotionAware zone owns both a ConvenienceAreaMotion and a SecurityAreaMotion
    service, and which of the two carries the motion state depends on how the zone
    is set up in the Hue app. The source is therefore resolved from the zone, and
    the state is unknown while neither service reports a valid one.
    """

    controller: SecurityAreaMotionController
    resource: SecurityAreaMotion

    entity_description = BinarySensorEntityDescription(
        key="motion_sensor", device_class=BinarySensorDeviceClass.MOTION
    )

    @property
    @override
    def name(self) -> str:
        """Return sensor name."""
        return self.controller.get_motion_area_configuration(self.resource.id).name

    @property
    @override
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        zone = self._motion_area_configuration
        # switching a zone off leaves the `enabled` flag of its services untouched,
        # so the zone is the only reliable signal that it stopped reporting motion
        if not zone.enabled or zone.health == MotionAreaHealth.NOT_RUNNING:
            return None
        # either service can be the one reporting a zone, with the other left holding
        # a reading that no longer changes, so take the first that has a valid one.
        # The convenience service comes first because a zone that is bound to lights
        # reports on that service.
        for source in (self._convenience_service, self.resource):
            if source is None or not source.enabled or source.motion is None:
                continue
            if (value := source.motion.value) is not None:
                return value
        return None

    def __init__(
        self,
        bridge: HueBridge,
        controller: SecurityAreaMotionController,
        resource: SecurityAreaMotion,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(bridge, controller, resource)
        # link the MotionAware sensor to the group the sensor is associated with
        self._motion_area_configuration = self.controller.get_motion_area_configuration(
            resource.id
        )
        group_id = self._motion_area_configuration.group.rid
        self.hue_group = self.bridge.api.groups[group_id]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.hue_group.id)},
        )

    @override
    async def async_added_to_hass(self) -> None:
        """Call when entity is added."""
        await super().async_added_to_hass()
        # subscribe to updates of the MotionAreaConfiguration to update the name
        self.async_on_remove(
            self.bridge.api.config.subscribe(
                self._handle_event, self._motion_area_configuration.id
            )
        )
        # zones that are bound to lights report their motion on the convenience service
        if (service_id := self._convenience_service_id) is not None:
            self.async_on_remove(
                self.bridge.api.sensors.convenience_area_motion.subscribe(
                    self._handle_event, service_id
                )
            )

    @property
    def _convenience_service_id(self) -> str | None:
        """Return the id of this zone's ConvenienceAreaMotion service, if it has one."""
        return next(
            (
                service.rid
                for service in self._motion_area_configuration.services
                if service.rtype == ResourceTypes.CONVENIENCE_AREA_MOTION
            ),
            None,
        )

    @property
    def _convenience_service(self) -> ConvenienceAreaMotion | None:
        """Return this zone's ConvenienceAreaMotion resource, if the bridge has it."""
        if (service_id := self._convenience_service_id) is None:
            return None
        return self.bridge.api.sensors.convenience_area_motion.get(service_id)


# pylint: disable-next=home-assistant-enforce-class-module
class HueEntertainmentActiveSensor(HueBaseEntity, BinarySensorEntity):
    """Representation of a Hue Entertainment Configuration as binary sensor."""

    controller: EntertainmentConfigurationController
    resource: EntertainmentConfiguration

    entity_description = BinarySensorEntityDescription(
        key="entertainment_active_sensor",
        device_class=BinarySensorDeviceClass.RUNNING,
        has_entity_name=True,
        translation_key="entertainment_area",
    )

    def __init__(
        self,
        bridge: HueBridge,
        controller: EntertainmentConfigurationController,
        resource: EntertainmentConfiguration,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(bridge, controller, resource)
        self._attr_translation_placeholders = {"area_name": resource.metadata.name}

    @property
    @override
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        return self.resource.status == EntertainmentStatus.ACTIVE

    @callback
    @override
    def on_update(self) -> None:
        """Call on update event."""
        self._attr_translation_placeholders = {"area_name": self.resource.metadata.name}
        # the entity name is cached, invalidate it so a rename
        # of the entertainment area in the Hue app is picked up
        self.__dict__.pop("name", None)


# pylint: disable-next=home-assistant-enforce-class-module
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
    @override
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        if not self.resource.enabled:
            # Force None (unknown) if the sensor is set to disabled in Hue
            return None
        return self.resource.contact_report.state != ContactState.CONTACT


# pylint: disable-next=home-assistant-enforce-class-module
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
    @override
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        if not self.resource.tamper_reports:
            return False
        return self.resource.tamper_reports[0].state == TamperState.TAMPERED
