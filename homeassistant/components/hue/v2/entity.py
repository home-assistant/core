"""Generic Hue Entity Model."""
from __future__ import annotations

from typing import TYPE_CHECKING, TypeAlias

from aiohue.v2.controllers.base import BaseResourcesController
from aiohue.v2.controllers.events import EventType
from aiohue.v2.models.resource import ResourceTypes
from aiohue.v2.models.zigbee_connectivity import ConnectivityServiceStatus

from homeassistant.core import callback
from homeassistant.helpers.device_registry import async_get as async_get_device_registry
from homeassistant.helpers.entity import DeviceInfo, Entity
from homeassistant.helpers.entity_registry import async_get as async_get_entity_registry

from ..bridge import HueBridge
from ..const import CONF_IGNORE_AVAILABILITY, DOMAIN

if TYPE_CHECKING:
    from aiohue.v2.models.device_power import DevicePower
    from aiohue.v2.models.grouped_light import GroupedLight
    from aiohue.v2.models.light import Light
    from aiohue.v2.models.light_level import LightLevel
    from aiohue.v2.models.motion import Motion

    HueResource: TypeAlias = Light | DevicePower | GroupedLight | LightLevel | Motion


RESOURCE_TYPE_NAMES = {
    # a simple mapping of hue resource type to Hass name
    ResourceTypes.LIGHT_LEVEL: "Illuminance",
    ResourceTypes.DEVICE_POWER: "Battery",
}


class HueBaseEntity(Entity):
    """Generic Entity Class for a Hue resource."""

    _attr_should_poll = False

    def __init__(
        self,
        bridge: HueBridge,
        controller: BaseResourcesController,
        resource: HueResource,
    ) -> None:
        """Initialize a generic Hue resource entity."""
        self.bridge = bridge
        self.controller = controller
        self.resource = resource
        self.device = controller.get_device(resource.id)
        self.logger = bridge.logger.getChild(resource.type.value)

        # Entity class attributes
        self._attr_unique_id = resource.id
        # device is precreated in main handler
        # this attaches the entity to the precreated device
        if self.device is None:
            # attach all device-less entities to the bridge itself
            # e.g. config based sensors like entertainment area
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, bridge.api.config.bridge.bridge_id)},
            )
        else:
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, self.device.id)},
            )
        # used for availability workaround
        self._ignore_availability = None
        self._last_state = None

    @property
    def name(self) -> str:
        """Return name for the entity."""
        if self.device is None:
            # this is just a guard
            # creating a pretty name for device-less entities (e.g. groups/scenes)
            # should be handled in the platform instead
            return self.resource.type.value
        dev_name = self.device.metadata.name
        # if resource is a light, use the device name itself
        if self.resource.type == ResourceTypes.LIGHT:
            return dev_name
        # for sensors etc, use devicename + pretty name of type
        type_title = RESOURCE_TYPE_NAMES.get(
            self.resource.type, self.resource.type.value.replace("_", " ").title()
        )
        return f"{dev_name} {type_title}"

    async def async_added_to_hass(self) -> None:
        """Call when entity is added."""
        self._check_availability()
        # Add value_changed callbacks.
        self.async_on_remove(
            self.controller.subscribe(
                self._handle_event,
                self.resource.id,
                (EventType.RESOURCE_UPDATED, EventType.RESOURCE_DELETED),
            )
        )
        # also subscribe to device update event to catch device changes (e.g. name)
        if self.device is None:
            return
        self.async_on_remove(
            self.bridge.api.devices.subscribe(
                self._handle_event,
                self.device.id,
                EventType.RESOURCE_UPDATED,
            )
        )
        # subscribe to zigbee_connectivity to catch availability changes
        if zigbee := self.bridge.api.devices.get_zigbee_connectivity(self.device.id):
            self.async_on_remove(
                self.bridge.api.sensors.zigbee_connectivity.subscribe(
                    self._handle_event,
                    zigbee.id,
                    EventType.RESOURCE_UPDATED,
                )
            )

    @property
    def available(self) -> bool:
        """Return entity availability."""
        # entities without a device attached should be always available
        if self.device is None:
            return True
        # the zigbee connectivity sensor itself should be always available
        if self.resource.type == ResourceTypes.ZIGBEE_CONNECTIVITY:
            return True
        if self._ignore_availability:
            return True
        # all device-attached entities get availability from the zigbee connectivity
        if zigbee := self.bridge.api.devices.get_zigbee_connectivity(self.device.id):
            return zigbee.status == ConnectivityServiceStatus.CONNECTED
        return True

    @callback
    def on_update(self) -> None:
        """Call on update event."""
        # used in subclasses

    @callback
    def _handle_event(self, event_type: EventType, resource: HueResource) -> None:
        """Handle status event for this resource (or it's parent)."""
        if event_type == EventType.RESOURCE_DELETED:
            # handle removal of room and zone 'virtual' devices/services
            # regular devices are removed automatically by the logic in device.py.
            if resource.type in (ResourceTypes.ROOM, ResourceTypes.ZONE):
                dev_reg = async_get_device_registry(self.hass)
                if device := dev_reg.async_get_device(
                    identifiers={(DOMAIN, resource.id)}
                ):
                    dev_reg.async_remove_device(device.id)
            # cleanup entities that are not strictly device-bound and have the bridge as parent
            if self.device is None:
                ent_reg = async_get_entity_registry(self.hass)
                ent_reg.async_remove(self.entity_id)
            return
        self.logger.debug("Received status update for %s", self.entity_id)
        self._check_availability()
        self.on_update()
        self.async_write_ha_state()

    @callback
    def _check_availability(self):
        """Check availability of the device."""
        # return if we already processed this entity
        if self._ignore_availability is not None:
            return
        # only do the availability check for entities connected to a device (with `on` feature)
        if self.device is None or not hasattr(self.resource, "on"):
            self._ignore_availability = False
            return
        # ignore availability if user added device to ignore list
        if self.device.id in self.bridge.config_entry.options.get(
            CONF_IGNORE_AVAILABILITY, []
        ):
            self._ignore_availability = True
            self.logger.info(
                "Device %s is configured to ignore availability status. ",
                self.name,
            )
            return
        # certified products (normally) report their state correctly
        # no need for workaround/reporting
        if self.device.product_data.certified:
            self._ignore_availability = False
            return
        # some (3th party) Hue lights report their connection status incorrectly
        # causing the zigbee availability to report as disconnected while in fact
        # it can be controlled. If the light is reported unavailable
        # by the zigbee connectivity but the state changes its considered as a
        # malfunctioning device and we report it.
        # While the user should actually fix this issue, we allow to
        # ignore the availability for this light/device from the config options.
        cur_state = self.resource.on.on
        if self._last_state is None:
            self._last_state = cur_state
            return
        if zigbee := self.bridge.api.devices.get_zigbee_connectivity(self.device.id):
            if (
                self._last_state != cur_state
                and zigbee.status != ConnectivityServiceStatus.CONNECTED
            ):
                # the device state changed from on->off or off->on
                # while it was reported as not connected!
                self.logger.warning(
                    (
                        "Device %s changed state while reported as disconnected. This"
                        " might be an indicator that routing is not working for this"
                        " device or the device is having connectivity issues. You can"
                        " disable availability reporting for this device in the Hue"
                        " options. Device details: %s - %s (%s) fw: %s"
                    ),
                    self.name,
                    self.device.product_data.manufacturer_name,
                    self.device.product_data.product_name,
                    self.device.product_data.model_id,
                    self.device.product_data.software_version,
                )
                # set attribute to false because we only want to log once per light/device.
                # a user must opt-in to ignore availability through integration options
                self._ignore_availability = False
        self._last_state = cur_state
