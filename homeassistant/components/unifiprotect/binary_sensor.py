"""This component provides binary sensors for UniFi Protect."""
from __future__ import annotations

from copy import copy
from dataclasses import dataclass
import logging
from typing import Any

from pyunifiprotect.data import NVR, Camera, Event, Light, Sensor

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_LAST_TRIP_TIME, ATTR_MODEL
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .data import ProtectData
from .entity import (
    EventThumbnailMixin,
    ProtectDeviceEntity,
    ProtectNVREntity,
    async_all_device_entities,
)
from .models import ProtectRequiredKeysMixin
from .utils import get_nested_attr

_LOGGER = logging.getLogger(__name__)


@dataclass
class ProtectBinaryEntityDescription(
    ProtectRequiredKeysMixin, BinarySensorEntityDescription
):
    """Describes UniFi Protect Binary Sensor entity."""


_KEY_DOORBELL = "doorbell"
_KEY_MOTION = "motion"
_KEY_DOOR = "door"
_KEY_DARK = "dark"
_KEY_BATTERY_LOW = "battery_low"
_KEY_DISK_HEALTH = "disk_health"


CAMERA_SENSORS: tuple[ProtectBinaryEntityDescription, ...] = (
    ProtectBinaryEntityDescription(
        key=_KEY_DOORBELL,
        name="Doorbell",
        device_class=BinarySensorDeviceClass.OCCUPANCY,
        icon="mdi:doorbell-video",
        ufp_required_field="feature_flags.has_chime",
        ufp_value="is_ringing",
    ),
    ProtectBinaryEntityDescription(
        key=_KEY_DARK,
        name="Is Dark",
        icon="mdi:brightness-6",
        ufp_value="is_dark",
    ),
)

LIGHT_SENSORS: tuple[ProtectBinaryEntityDescription, ...] = (
    ProtectBinaryEntityDescription(
        key=_KEY_DARK,
        name="Is Dark",
        icon="mdi:brightness-6",
        ufp_value="is_dark",
    ),
    ProtectBinaryEntityDescription(
        key=_KEY_MOTION,
        name="Motion Detected",
        device_class=BinarySensorDeviceClass.MOTION,
        ufp_value="is_pir_motion_detected",
    ),
)

SENSE_SENSORS: tuple[ProtectBinaryEntityDescription, ...] = (
    ProtectBinaryEntityDescription(
        key=_KEY_DOOR,
        name="Door",
        device_class=BinarySensorDeviceClass.DOOR,
        ufp_value="is_opened",
    ),
    ProtectBinaryEntityDescription(
        key=_KEY_BATTERY_LOW,
        name="Battery low",
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_value="battery_status.is_low",
    ),
    ProtectBinaryEntityDescription(
        key=_KEY_MOTION,
        name="Motion Detected",
        device_class=BinarySensorDeviceClass.MOTION,
        ufp_value="is_motion_detected",
    ),
)

MOTION_SENSORS: tuple[ProtectBinaryEntityDescription, ...] = (
    ProtectBinaryEntityDescription(
        key=_KEY_MOTION,
        name="Motion",
        device_class=BinarySensorDeviceClass.MOTION,
        ufp_value="is_motion_detected",
    ),
)


DISK_SENSORS: tuple[ProtectBinaryEntityDescription, ...] = (
    ProtectBinaryEntityDescription(
        key=_KEY_DISK_HEALTH,
        name="Disk {index} Health",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensors for UniFi Protect integration."""
    data: ProtectData = hass.data[DOMAIN][entry.entry_id]
    entities: list[ProtectDeviceEntity] = async_all_device_entities(
        data,
        ProtectDeviceBinarySensor,
        camera_descs=CAMERA_SENSORS,
        light_descs=LIGHT_SENSORS,
        sense_descs=SENSE_SENSORS,
    )
    entities += _async_motion_entities(data)
    entities += _async_nvr_entities(data)

    async_add_entities(entities)


@callback
def _async_motion_entities(
    data: ProtectData,
) -> list[ProtectDeviceEntity]:
    entities: list[ProtectDeviceEntity] = []
    for device in data.api.bootstrap.cameras.values():
        for description in MOTION_SENSORS:
            entities.append(ProtectEventBinarySensor(data, device, description))
            _LOGGER.debug(
                "Adding binary sensor entity %s for %s",
                description.name,
                device.name,
            )

    return entities


@callback
def _async_nvr_entities(
    data: ProtectData,
) -> list[ProtectDeviceEntity]:
    entities: list[ProtectDeviceEntity] = []
    device = data.api.bootstrap.nvr
    for index, _ in enumerate(device.system_info.storage.devices):
        for description in DISK_SENSORS:
            entities.append(
                ProtectDiskBinarySensor(data, device, description, index=index)
            )
            _LOGGER.debug(
                "Adding binary sensor entity %s",
                (description.name or "{index}").format(index=index),
            )

    return entities


class ProtectDeviceBinarySensor(ProtectDeviceEntity, BinarySensorEntity):
    """A UniFi Protect Device Binary Sensor."""

    def __init__(
        self,
        data: ProtectData,
        description: ProtectBinaryEntityDescription,
        device: Camera | Light | Sensor | None = None,
    ) -> None:
        """Initialize the Binary Sensor."""

        if device and not hasattr(self, "device"):
            self.device: Camera | Light | Sensor = device
        self.entity_description: ProtectBinaryEntityDescription = description
        super().__init__(data)

    @callback
    def _async_update_extra_attrs_from_protect(self) -> dict[str, Any]:
        attrs: dict[str, Any] = {}
        key = self.entity_description.key

        if key == _KEY_DARK:
            return attrs

        if isinstance(self.device, Camera):
            if key == _KEY_DOORBELL:
                attrs[ATTR_LAST_TRIP_TIME] = self.device.last_ring
            elif key == _KEY_MOTION:
                attrs[ATTR_LAST_TRIP_TIME] = self.device.last_motion
        elif isinstance(self.device, Sensor):
            if key in (_KEY_MOTION, _KEY_DOOR):
                if key == _KEY_MOTION:
                    last_trip = self.device.motion_detected_at
                else:
                    last_trip = self.device.open_status_changed_at

                attrs[ATTR_LAST_TRIP_TIME] = last_trip
        elif isinstance(self.device, Light):
            if key == _KEY_MOTION:
                attrs[ATTR_LAST_TRIP_TIME] = self.device.last_motion

        return attrs

    @callback
    def _async_update_device_from_protect(self) -> None:
        super()._async_update_device_from_protect()

        assert self.entity_description.ufp_value is not None

        self._attr_is_on = get_nested_attr(
            self.device, self.entity_description.ufp_value
        )
        attrs = self.extra_state_attributes or {}
        self._attr_extra_state_attributes = {
            **attrs,
            **self._async_update_extra_attrs_from_protect(),
        }


class ProtectDiskBinarySensor(ProtectNVREntity, BinarySensorEntity):
    """A UniFi Protect NVR Disk Binary Sensor."""

    def __init__(
        self,
        data: ProtectData,
        device: NVR,
        description: ProtectBinaryEntityDescription,
        index: int,
    ) -> None:
        """Initialize the Binary Sensor."""
        description = copy(description)
        description.key = f"{description.key}_{index}"
        description.name = (description.name or "{index}").format(index=index)
        self._index = index
        self.entity_description: ProtectBinaryEntityDescription = description
        super().__init__(data, device)

    @callback
    def _async_update_device_from_protect(self) -> None:
        super()._async_update_device_from_protect()

        disks = self.device.system_info.storage.devices
        disk_available = len(disks) > self._index
        self._attr_available = self._attr_available and disk_available
        if disk_available:
            disk = disks[self._index]
            self._attr_is_on = not disk.healthy
            self._attr_extra_state_attributes = {ATTR_MODEL: disk.model}


class ProtectEventBinarySensor(EventThumbnailMixin, ProtectDeviceBinarySensor):
    """A UniFi Protect Device Binary Sensor with access tokens."""

    def __init__(
        self,
        data: ProtectData,
        device: Camera,
        description: ProtectBinaryEntityDescription,
    ) -> None:
        """Init a binary sensor that uses access tokens."""
        self.device: Camera = device
        super().__init__(data, description=description)

    @callback
    def _async_get_event(self) -> Event | None:
        """Get event from Protect device."""

        event: Event | None = None
        if self.device.is_motion_detected and self.device.last_motion_event is not None:
            event = self.device.last_motion_event

        return event
