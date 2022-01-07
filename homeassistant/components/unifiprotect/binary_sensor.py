"""This component provides binary sensors for UniFi Protect."""
from __future__ import annotations

from copy import copy
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from typing import Any, Final

from pyunifiprotect.data import NVR, Camera, Light, Sensor

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_DOOR,
    DEVICE_CLASS_MOTION,
    DEVICE_CLASS_PROBLEM,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_LAST_TRIP_TIME, ATTR_MODEL
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_call_later
from homeassistant.util.dt import utcnow

from .const import DOMAIN
from .data import ProtectData
from .entity import ProtectDeviceEntity, ProtectNVREntity, async_all_device_entities
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

DEVICE_CLASS_RING: Final = "unifiprotect__ring"
RING_INTERVAL = timedelta(seconds=3)


CAMERA_SENSORS: tuple[ProtectBinaryEntityDescription, ...] = (
    ProtectBinaryEntityDescription(
        key=_KEY_DOORBELL,
        name="Doorbell Chime",
        device_class=DEVICE_CLASS_RING,
        icon="mdi:doorbell-video",
        ufp_required_field="feature_flags.has_chime",
        ufp_value="last_ring",
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
        device_class=DEVICE_CLASS_MOTION,
        ufp_value="is_pir_motion_detected",
    ),
)

SENSE_SENSORS: tuple[ProtectBinaryEntityDescription, ...] = (
    ProtectBinaryEntityDescription(
        key=_KEY_DOOR,
        name="Door",
        device_class=DEVICE_CLASS_DOOR,
        ufp_value="is_opened",
    ),
    ProtectBinaryEntityDescription(
        key=_KEY_BATTERY_LOW,
        name="Battery low",
        device_class=DEVICE_CLASS_BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_value="battery_status.is_low",
    ),
    ProtectBinaryEntityDescription(
        key=_KEY_MOTION,
        name="Motion Detected",
        device_class=DEVICE_CLASS_MOTION,
        ufp_value="is_motion_detected",
    ),
)

DISK_SENSORS: tuple[ProtectBinaryEntityDescription, ...] = (
    ProtectBinaryEntityDescription(
        key=_KEY_DISK_HEALTH,
        name="Disk {index} Health",
        device_class=DEVICE_CLASS_PROBLEM,
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
    entities += _async_nvr_entities(data)

    async_add_entities(entities)


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
        self._doorbell_callback: CALLBACK_TYPE | None = None

    @callback
    def _async_update_extra_attrs_from_protect(self) -> dict[str, Any]:
        attrs: dict[str, Any] = {}
        key = self.entity_description.key

        if key == _KEY_DARK:
            return attrs

        if key == _KEY_DOORBELL:
            assert isinstance(self.device, Camera)
            attrs[ATTR_LAST_TRIP_TIME] = self.device.last_ring
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

        self._attr_extra_state_attributes = (
            self._async_update_extra_attrs_from_protect()
        )

        if self.entity_description.key == _KEY_DOORBELL:
            last_ring = get_nested_attr(self.device, self.entity_description.ufp_value)
            now = utcnow()

            is_ringing = (
                False if last_ring is None else (now - last_ring) < RING_INTERVAL
            )
            _LOGGER.warning("%s, %s, %s", last_ring, now, is_ringing)
            if is_ringing:
                self._async_cancel_doorbell_callback()
                self._doorbell_callback = async_call_later(
                    self.hass, RING_INTERVAL, self._async_reset_doorbell
                )
            self._attr_is_on = is_ringing
        else:
            self._attr_is_on = get_nested_attr(
                self.device, self.entity_description.ufp_value
            )

    @callback
    def _async_cancel_doorbell_callback(self) -> None:
        if self._doorbell_callback is not None:
            _LOGGER.debug("Canceling doorbell ring callback")
            self._doorbell_callback()
            self._doorbell_callback = None

    async def _async_reset_doorbell(self, now: datetime) -> None:
        _LOGGER.debug("Doorbell ring ended")
        self._doorbell_callback = None
        self._async_updated_event()

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        self._async_cancel_doorbell_callback()
        return await super().async_will_remove_from_hass()


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
