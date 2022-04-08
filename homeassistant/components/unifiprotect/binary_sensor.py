"""This component provides binary sensors for UniFi Protect."""
from __future__ import annotations

from copy import copy
from dataclasses import dataclass
import logging

from pyunifiprotect.data import NVR, Camera, Event, Light, MountType, Sensor

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_MODEL
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

_LOGGER = logging.getLogger(__name__)
_KEY_DOOR = "door"


@dataclass
class ProtectBinaryEntityDescription(
    ProtectRequiredKeysMixin, BinarySensorEntityDescription
):
    """Describes UniFi Protect Binary Sensor entity."""


MOUNT_DEVICE_CLASS_MAP = {
    MountType.GARAGE: BinarySensorDeviceClass.GARAGE_DOOR,
    MountType.WINDOW: BinarySensorDeviceClass.WINDOW,
    MountType.DOOR: BinarySensorDeviceClass.DOOR,
}


CAMERA_SENSORS: tuple[ProtectBinaryEntityDescription, ...] = (
    ProtectBinaryEntityDescription(
        key="doorbell",
        name="Doorbell",
        device_class=BinarySensorDeviceClass.OCCUPANCY,
        icon="mdi:doorbell-video",
        ufp_required_field="feature_flags.has_chime",
        ufp_value="is_ringing",
    ),
    ProtectBinaryEntityDescription(
        key="dark",
        name="Is Dark",
        icon="mdi:brightness-6",
        ufp_value="is_dark",
    ),
)

LIGHT_SENSORS: tuple[ProtectBinaryEntityDescription, ...] = (
    ProtectBinaryEntityDescription(
        key="dark",
        name="Is Dark",
        icon="mdi:brightness-6",
        ufp_value="is_dark",
    ),
    ProtectBinaryEntityDescription(
        key="motion",
        name="Motion Detected",
        device_class=BinarySensorDeviceClass.MOTION,
        ufp_value="is_pir_motion_detected",
    ),
)

SENSE_SENSORS: tuple[ProtectBinaryEntityDescription, ...] = (
    ProtectBinaryEntityDescription(
        key=_KEY_DOOR,
        name="Contact",
        device_class=BinarySensorDeviceClass.DOOR,
        ufp_value="is_opened",
        ufp_enabled="is_contact_sensor_enabled",
    ),
    ProtectBinaryEntityDescription(
        key="battery_low",
        name="Battery low",
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_value="battery_status.is_low",
    ),
    ProtectBinaryEntityDescription(
        key="motion",
        name="Motion Detected",
        device_class=BinarySensorDeviceClass.MOTION,
        ufp_value="is_motion_detected",
        ufp_enabled="is_motion_sensor_enabled",
    ),
    ProtectBinaryEntityDescription(
        key="tampering",
        name="Tampering Detected",
        device_class=BinarySensorDeviceClass.TAMPER,
        ufp_value="is_tampering_detected",
    ),
)

MOTION_SENSORS: tuple[ProtectBinaryEntityDescription, ...] = (
    ProtectBinaryEntityDescription(
        key="motion",
        name="Motion",
        device_class=BinarySensorDeviceClass.MOTION,
        ufp_value="is_motion_detected",
    ),
)

DOORLOCK_SENSORS: tuple[ProtectBinaryEntityDescription, ...] = (
    ProtectBinaryEntityDescription(
        key="battery_low",
        name="Battery low",
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_value="battery_status.is_low",
    ),
)


DISK_SENSORS: tuple[ProtectBinaryEntityDescription, ...] = (
    ProtectBinaryEntityDescription(
        key="disk_health",
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
        lock_descs=DOORLOCK_SENSORS,
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

    device: Camera | Light | Sensor
    entity_description: ProtectBinaryEntityDescription

    @callback
    def _async_update_device_from_protect(self) -> None:
        super()._async_update_device_from_protect()

        self._attr_is_on = self.entity_description.get_ufp_value(self.device)
        # UP Sense can be any of the 3 contact sensor device classes
        if self.entity_description.key == _KEY_DOOR and isinstance(self.device, Sensor):
            self.entity_description.device_class = MOUNT_DEVICE_CLASS_MAP.get(
                self.device.mount_type, BinarySensorDeviceClass.DOOR
            )


class ProtectDiskBinarySensor(ProtectNVREntity, BinarySensorEntity):
    """A UniFi Protect NVR Disk Binary Sensor."""

    entity_description: ProtectBinaryEntityDescription

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
        super().__init__(data, device, description)

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

    device: Camera

    @callback
    def _async_get_event(self) -> Event | None:
        """Get event from Protect device."""

        event: Event | None = None
        if self.device.is_motion_detected and self.device.last_motion_event is not None:
            event = self.device.last_motion_event

        return event
