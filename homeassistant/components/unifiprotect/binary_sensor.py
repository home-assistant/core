"""Component providing binary sensors for UniFi Protect."""
from __future__ import annotations

import dataclasses
import logging
from typing import Any

from pyunifiprotect.data import (
    NVR,
    Camera,
    Light,
    ModelType,
    MountType,
    ProtectAdoptableDeviceModel,
    ProtectModelWithId,
    Sensor,
)
from pyunifiprotect.data.nvr import UOSDisk

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DISPATCH_ADOPT, DOMAIN
from .data import ProtectData
from .entity import (
    EventEntityMixin,
    ProtectDeviceEntity,
    ProtectNVREntity,
    async_all_device_entities,
)
from .models import PermRequired, ProtectEventMixin, ProtectRequiredKeysMixin
from .utils import async_dispatch_id as _ufpd

_LOGGER = logging.getLogger(__name__)
_KEY_DOOR = "door"


@dataclasses.dataclass(frozen=True, kw_only=True)
class ProtectBinaryEntityDescription(
    ProtectRequiredKeysMixin, BinarySensorEntityDescription
):
    """Describes UniFi Protect Binary Sensor entity."""


@dataclasses.dataclass(frozen=True, kw_only=True)
class ProtectBinaryEventEntityDescription(
    ProtectEventMixin, BinarySensorEntityDescription
):
    """Describes UniFi Protect Binary Sensor entity."""


MOUNT_DEVICE_CLASS_MAP = {
    MountType.GARAGE: BinarySensorDeviceClass.GARAGE_DOOR,
    MountType.WINDOW: BinarySensorDeviceClass.WINDOW,
    MountType.DOOR: BinarySensorDeviceClass.DOOR,
}


CAMERA_SENSORS: tuple[ProtectBinaryEntityDescription, ...] = (
    ProtectBinaryEntityDescription(
        key="dark",
        name="Is Dark",
        icon="mdi:brightness-6",
        ufp_value="is_dark",
    ),
    ProtectBinaryEntityDescription(
        key="ssh",
        name="SSH Enabled",
        icon="mdi:lock",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_value="is_ssh_enabled",
        ufp_perm=PermRequired.NO_WRITE,
    ),
    ProtectBinaryEntityDescription(
        key="status_light",
        name="Status Light On",
        icon="mdi:led-on",
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_required_field="feature_flags.has_led_status",
        ufp_value="led_settings.is_enabled",
        ufp_perm=PermRequired.NO_WRITE,
    ),
    ProtectBinaryEntityDescription(
        key="hdr_mode",
        name="HDR Mode",
        icon="mdi:brightness-7",
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_required_field="feature_flags.has_hdr",
        ufp_value="hdr_mode",
        ufp_perm=PermRequired.NO_WRITE,
    ),
    ProtectBinaryEntityDescription(
        key="high_fps",
        name="High FPS",
        icon="mdi:video-high-definition",
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_required_field="feature_flags.has_highfps",
        ufp_value="is_high_fps_enabled",
        ufp_perm=PermRequired.NO_WRITE,
    ),
    ProtectBinaryEntityDescription(
        key="system_sounds",
        name="System Sounds",
        icon="mdi:speaker",
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_required_field="has_speaker",
        ufp_value="speaker_settings.are_system_sounds_enabled",
        ufp_enabled="feature_flags.has_speaker",
        ufp_perm=PermRequired.NO_WRITE,
    ),
    ProtectBinaryEntityDescription(
        key="osd_name",
        name="Overlay: Show Name",
        icon="mdi:fullscreen",
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_value="osd_settings.is_name_enabled",
        ufp_perm=PermRequired.NO_WRITE,
    ),
    ProtectBinaryEntityDescription(
        key="osd_date",
        name="Overlay: Show Date",
        icon="mdi:fullscreen",
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_value="osd_settings.is_date_enabled",
        ufp_perm=PermRequired.NO_WRITE,
    ),
    ProtectBinaryEntityDescription(
        key="osd_logo",
        name="Overlay: Show Logo",
        icon="mdi:fullscreen",
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_value="osd_settings.is_logo_enabled",
        ufp_perm=PermRequired.NO_WRITE,
    ),
    ProtectBinaryEntityDescription(
        key="osd_bitrate",
        name="Overlay: Show Bitrate",
        icon="mdi:fullscreen",
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_value="osd_settings.is_debug_enabled",
        ufp_perm=PermRequired.NO_WRITE,
    ),
    ProtectBinaryEntityDescription(
        key="motion_enabled",
        name="Detections: Motion",
        icon="mdi:run-fast",
        ufp_value="recording_settings.enable_motion_detection",
        ufp_perm=PermRequired.NO_WRITE,
    ),
    ProtectBinaryEntityDescription(
        key="smart_person",
        name="Detections: Person",
        icon="mdi:walk",
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_required_field="can_detect_person",
        ufp_value="is_person_detection_on",
        ufp_perm=PermRequired.NO_WRITE,
    ),
    ProtectBinaryEntityDescription(
        key="smart_vehicle",
        name="Detections: Vehicle",
        icon="mdi:car",
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_required_field="can_detect_vehicle",
        ufp_value="is_vehicle_detection_on",
        ufp_perm=PermRequired.NO_WRITE,
    ),
    ProtectBinaryEntityDescription(
        key="smart_package",
        name="Detections: Package",
        icon="mdi:package-variant-closed",
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_required_field="can_detect_package",
        ufp_value="is_package_detection_on",
        ufp_perm=PermRequired.NO_WRITE,
    ),
    ProtectBinaryEntityDescription(
        key="smart_licenseplate",
        name="Detections: License Plate",
        icon="mdi:car",
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_required_field="can_detect_license_plate",
        ufp_value="is_license_plate_detection_on",
        ufp_perm=PermRequired.NO_WRITE,
    ),
    ProtectBinaryEntityDescription(
        key="smart_smoke",
        name="Detections: Smoke",
        icon="mdi:fire",
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_required_field="can_detect_smoke",
        ufp_value="is_smoke_detection_on",
        ufp_perm=PermRequired.NO_WRITE,
    ),
    ProtectBinaryEntityDescription(
        key="smart_cmonx",
        name="Detections: CO",
        icon="mdi:molecule-co",
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_required_field="can_detect_co",
        ufp_value="is_co_detection_on",
        ufp_perm=PermRequired.NO_WRITE,
    ),
    ProtectBinaryEntityDescription(
        key="smart_siren",
        name="Detections: Siren",
        icon="mdi:alarm-bell",
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_required_field="can_detect_siren",
        ufp_value="is_siren_detection_on",
        ufp_perm=PermRequired.NO_WRITE,
    ),
    ProtectBinaryEntityDescription(
        key="smart_baby_cry",
        name="Detections: Baby Cry",
        icon="mdi:cradle",
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_required_field="can_detect_baby_cry",
        ufp_value="is_baby_cry_detection_on",
        ufp_perm=PermRequired.NO_WRITE,
    ),
    ProtectBinaryEntityDescription(
        key="smart_speak",
        name="Detections: Speaking",
        icon="mdi:account-voice",
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_required_field="can_detect_speaking",
        ufp_value="is_speaking_detection_on",
        ufp_perm=PermRequired.NO_WRITE,
    ),
    ProtectBinaryEntityDescription(
        key="smart_bark",
        name="Detections: Barking",
        icon="mdi:dog",
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_required_field="can_detect_bark",
        ufp_value="is_bark_detection_on",
        ufp_perm=PermRequired.NO_WRITE,
    ),
    ProtectBinaryEntityDescription(
        key="smart_car_alarm",
        name="Detections: Car Alarm",
        icon="mdi:car",
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_required_field="can_detect_car_alarm",
        ufp_value="is_car_alarm_detection_on",
        ufp_perm=PermRequired.NO_WRITE,
    ),
    ProtectBinaryEntityDescription(
        key="smart_car_horn",
        name="Detections: Car Horn",
        icon="mdi:bugle",
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_required_field="can_detect_car_horn",
        ufp_value="is_car_horn_detection_on",
        ufp_perm=PermRequired.NO_WRITE,
    ),
    ProtectBinaryEntityDescription(
        key="smart_glass_break",
        name="Detections: Glass Break",
        icon="mdi:glass-fragile",
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_required_field="can_detect_glass_break",
        ufp_value="is_glass_break_detection_on",
        ufp_perm=PermRequired.NO_WRITE,
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
    ProtectBinaryEntityDescription(
        key="light",
        name="Flood Light",
        icon="mdi:spotlight-beam",
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_value="is_light_on",
        ufp_perm=PermRequired.NO_WRITE,
    ),
    ProtectBinaryEntityDescription(
        key="ssh",
        name="SSH Enabled",
        icon="mdi:lock",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_value="is_ssh_enabled",
        ufp_perm=PermRequired.NO_WRITE,
    ),
    ProtectBinaryEntityDescription(
        key="status_light",
        name="Status Light On",
        icon="mdi:led-on",
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_value="light_device_settings.is_indicator_enabled",
        ufp_perm=PermRequired.NO_WRITE,
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
        key="leak",
        name="Leak",
        device_class=BinarySensorDeviceClass.MOISTURE,
        ufp_value="is_leak_detected",
        ufp_enabled="is_leak_sensor_enabled",
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
    ProtectBinaryEntityDescription(
        key="status_light",
        name="Status Light On",
        icon="mdi:led-on",
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_value="led_settings.is_enabled",
        ufp_perm=PermRequired.NO_WRITE,
    ),
    ProtectBinaryEntityDescription(
        key="motion_enabled",
        name="Motion Detection",
        icon="mdi:walk",
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_value="motion_settings.is_enabled",
        ufp_perm=PermRequired.NO_WRITE,
    ),
    ProtectBinaryEntityDescription(
        key="temperature",
        name="Temperature Sensor",
        icon="mdi:thermometer",
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_value="temperature_settings.is_enabled",
        ufp_perm=PermRequired.NO_WRITE,
    ),
    ProtectBinaryEntityDescription(
        key="humidity",
        name="Humidity Sensor",
        icon="mdi:water-percent",
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_value="humidity_settings.is_enabled",
        ufp_perm=PermRequired.NO_WRITE,
    ),
    ProtectBinaryEntityDescription(
        key="light",
        name="Light Sensor",
        icon="mdi:brightness-5",
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_value="light_settings.is_enabled",
        ufp_perm=PermRequired.NO_WRITE,
    ),
    ProtectBinaryEntityDescription(
        key="alarm",
        name="Alarm Sound Detection",
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_value="alarm_settings.is_enabled",
        ufp_perm=PermRequired.NO_WRITE,
    ),
)

EVENT_SENSORS: tuple[ProtectBinaryEventEntityDescription, ...] = (
    ProtectBinaryEventEntityDescription(
        key="doorbell",
        name="Doorbell",
        device_class=BinarySensorDeviceClass.OCCUPANCY,
        icon="mdi:doorbell-video",
        ufp_required_field="feature_flags.is_doorbell",
        ufp_value="is_ringing",
        ufp_event_obj="last_ring_event",
    ),
    ProtectBinaryEventEntityDescription(
        key="motion",
        name="Motion",
        device_class=BinarySensorDeviceClass.MOTION,
        ufp_value="is_motion_currently_detected",
        ufp_enabled="is_motion_detection_on",
        ufp_event_obj="last_motion_event",
    ),
    ProtectBinaryEventEntityDescription(
        key="smart_obj_any",
        name="Object Detected",
        icon="mdi:eye",
        ufp_value="is_smart_currently_detected",
        ufp_required_field="feature_flags.has_smart_detect",
        ufp_event_obj="last_smart_detect_event",
    ),
    ProtectBinaryEventEntityDescription(
        key="smart_obj_person",
        name="Person Detected",
        icon="mdi:walk",
        ufp_value="is_person_currently_detected",
        ufp_required_field="can_detect_person",
        ufp_enabled="is_person_detection_on",
        ufp_event_obj="last_person_detect_event",
    ),
    ProtectBinaryEventEntityDescription(
        key="smart_obj_vehicle",
        name="Vehicle Detected",
        icon="mdi:car",
        ufp_value="is_vehicle_currently_detected",
        ufp_required_field="can_detect_vehicle",
        ufp_enabled="is_vehicle_detection_on",
        ufp_event_obj="last_vehicle_detect_event",
    ),
    ProtectBinaryEventEntityDescription(
        key="smart_obj_package",
        name="Package Detected",
        icon="mdi:package-variant-closed",
        ufp_value="is_package_currently_detected",
        ufp_required_field="can_detect_package",
        ufp_enabled="is_package_detection_on",
        ufp_event_obj="last_package_detect_event",
    ),
    ProtectBinaryEventEntityDescription(
        key="smart_audio_any",
        name="Audio Object Detected",
        icon="mdi:eye",
        ufp_value="is_audio_currently_detected",
        ufp_required_field="feature_flags.has_smart_detect",
        ufp_event_obj="last_smart_audio_detect_event",
    ),
    ProtectBinaryEventEntityDescription(
        key="smart_audio_smoke",
        name="Smoke Alarm Detected",
        icon="mdi:fire",
        ufp_value="is_smoke_currently_detected",
        ufp_required_field="can_detect_smoke",
        ufp_enabled="is_smoke_detection_on",
        ufp_event_obj="last_smoke_detect_event",
    ),
    ProtectBinaryEventEntityDescription(
        key="smart_audio_cmonx",
        name="CO Alarm Detected",
        icon="mdi:molecule-co",
        ufp_value="is_cmonx_currently_detected",
        ufp_required_field="can_detect_co",
        ufp_enabled="is_co_detection_on",
        ufp_event_obj="last_cmonx_detect_event",
    ),
    ProtectBinaryEventEntityDescription(
        key="smart_audio_siren",
        name="Siren Detected",
        icon="mdi:alarm-bell",
        ufp_value="is_siren_currently_detected",
        ufp_required_field="can_detect_siren",
        ufp_enabled="is_siren_detection_on",
        ufp_event_obj="last_siren_detect_event",
    ),
    ProtectBinaryEventEntityDescription(
        key="smart_audio_baby_cry",
        name="Baby Cry Detected",
        icon="mdi:cradle",
        ufp_value="is_baby_cry_currently_detected",
        ufp_required_field="can_detect_baby_cry",
        ufp_enabled="is_baby_cry_detection_on",
        ufp_event_obj="last_baby_cry_detect_event",
    ),
    ProtectBinaryEventEntityDescription(
        key="smart_audio_speak",
        name="Speaking Detected",
        icon="mdi:account-voice",
        ufp_value="is_speaking_currently_detected",
        ufp_required_field="can_detect_speaking",
        ufp_enabled="is_speaking_detection_on",
        ufp_event_obj="last_speaking_detect_event",
    ),
    ProtectBinaryEventEntityDescription(
        key="smart_audio_bark",
        name="Barking Detected",
        icon="mdi:dog",
        ufp_value="is_bark_currently_detected",
        ufp_required_field="can_detect_bark",
        ufp_enabled="is_bark_detection_on",
        ufp_event_obj="last_bark_detect_event",
    ),
    ProtectBinaryEventEntityDescription(
        key="smart_audio_car_alarm",
        name="Car Alarm Detected",
        icon="mdi:car",
        ufp_value="is_car_alarm_currently_detected",
        ufp_required_field="can_detect_car_alarm",
        ufp_enabled="is_car_alarm_detection_on",
        ufp_event_obj="last_car_alarm_detect_event",
    ),
    ProtectBinaryEventEntityDescription(
        key="smart_audio_car_horn",
        name="Car Horn Detected",
        icon="mdi:bugle",
        ufp_value="is_car_horn_currently_detected",
        ufp_required_field="can_detect_car_horn",
        ufp_enabled="is_car_horn_detection_on",
        ufp_event_obj="last_car_horn_detect_event",
    ),
    ProtectBinaryEventEntityDescription(
        key="smart_audio_glass_break",
        name="Glass Break Detected",
        icon="mdi:glass-fragile",
        ufp_value="last_glass_break_detect",
        ufp_required_field="can_detect_glass_break",
        ufp_enabled="is_glass_break_detection_on",
        ufp_event_obj="last_glass_break_detect_event",
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
    ProtectBinaryEntityDescription(
        key="status_light",
        name="Status Light On",
        icon="mdi:led-on",
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_value="led_settings.is_enabled",
        ufp_perm=PermRequired.NO_WRITE,
    ),
)

VIEWER_SENSORS: tuple[ProtectBinaryEntityDescription, ...] = (
    ProtectBinaryEntityDescription(
        key="ssh",
        name="SSH Enabled",
        icon="mdi:lock",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_value="is_ssh_enabled",
        ufp_perm=PermRequired.NO_WRITE,
    ),
)


DISK_SENSORS: tuple[ProtectBinaryEntityDescription, ...] = (
    ProtectBinaryEntityDescription(
        key="disk_health",
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

    async def _add_new_device(device: ProtectAdoptableDeviceModel) -> None:
        entities: list[ProtectDeviceEntity] = async_all_device_entities(
            data,
            ProtectDeviceBinarySensor,
            camera_descs=CAMERA_SENSORS,
            light_descs=LIGHT_SENSORS,
            sense_descs=SENSE_SENSORS,
            lock_descs=DOORLOCK_SENSORS,
            viewer_descs=VIEWER_SENSORS,
            ufp_device=device,
        )
        if device.is_adopted and isinstance(device, Camera):
            entities += _async_event_entities(data, ufp_device=device)
        async_add_entities(entities)

    entry.async_on_unload(
        async_dispatcher_connect(hass, _ufpd(entry, DISPATCH_ADOPT), _add_new_device)
    )

    entities: list[ProtectDeviceEntity] = async_all_device_entities(
        data,
        ProtectDeviceBinarySensor,
        camera_descs=CAMERA_SENSORS,
        light_descs=LIGHT_SENSORS,
        sense_descs=SENSE_SENSORS,
        lock_descs=DOORLOCK_SENSORS,
        viewer_descs=VIEWER_SENSORS,
    )
    entities += _async_event_entities(data)
    entities += _async_nvr_entities(data)

    async_add_entities(entities)


@callback
def _async_event_entities(
    data: ProtectData,
    ufp_device: ProtectAdoptableDeviceModel | None = None,
) -> list[ProtectDeviceEntity]:
    entities: list[ProtectDeviceEntity] = []
    devices = (
        data.get_by_types({ModelType.CAMERA}) if ufp_device is None else [ufp_device]
    )
    for device in devices:
        for description in EVENT_SENSORS:
            if not description.has_required(device):
                continue
            entities.append(ProtectEventBinarySensor(data, device, description))
            _LOGGER.debug(
                "Adding binary sensor entity %s for %s",
                description.name,
                device.display_name,
            )

    return entities


@callback
def _async_nvr_entities(
    data: ProtectData,
) -> list[ProtectDeviceEntity]:
    entities: list[ProtectDeviceEntity] = []
    device = data.api.bootstrap.nvr
    if device.system_info.ustorage is None:
        return entities

    for disk in device.system_info.ustorage.disks:
        for description in DISK_SENSORS:
            if not disk.has_disk:
                continue

            entities.append(ProtectDiskBinarySensor(data, device, description, disk))
            _LOGGER.debug(
                "Adding binary sensor entity %s",
                f"{disk.type} {disk.slot}",
            )

    return entities


class ProtectDeviceBinarySensor(ProtectDeviceEntity, BinarySensorEntity):
    """A UniFi Protect Device Binary Sensor."""

    device: Camera | Light | Sensor
    entity_description: ProtectBinaryEntityDescription

    @callback
    def _async_update_device_from_protect(self, device: ProtectModelWithId) -> None:
        super()._async_update_device_from_protect(device)
        entity_description = self.entity_description
        updated_device = self.device
        self._attr_is_on = entity_description.get_ufp_value(updated_device)
        # UP Sense can be any of the 3 contact sensor device classes
        if entity_description.key == _KEY_DOOR and isinstance(updated_device, Sensor):
            self._attr_device_class = MOUNT_DEVICE_CLASS_MAP.get(
                updated_device.mount_type, BinarySensorDeviceClass.DOOR
            )
        else:
            self._attr_device_class = self.entity_description.device_class

    @callback
    def _async_get_state_attrs(self) -> tuple[Any, ...]:
        """Retrieve data that goes into the current state of the entity.

        Called before and after updating entity and state is only written if there
        is a change.
        """

        return (self._attr_available, self._attr_is_on, self._attr_device_class)


class ProtectDiskBinarySensor(ProtectNVREntity, BinarySensorEntity):
    """A UniFi Protect NVR Disk Binary Sensor."""

    _disk: UOSDisk
    entity_description: ProtectBinaryEntityDescription

    def __init__(
        self,
        data: ProtectData,
        device: NVR,
        description: ProtectBinaryEntityDescription,
        disk: UOSDisk,
    ) -> None:
        """Initialize the Binary Sensor."""
        self._disk = disk
        # backwards compat with old unique IDs
        index = self._disk.slot - 1

        description = dataclasses.replace(
            description,
            key=f"{description.key}_{index}",
            name=f"{disk.type} {disk.slot}",
        )
        super().__init__(data, device, description)

    @callback
    def _async_update_device_from_protect(self, device: ProtectModelWithId) -> None:
        super()._async_update_device_from_protect(device)

        slot = self._disk.slot
        self._attr_available = False

        # should not be possible since it would require user to
        # _downgrade_ to make ustorage disppear
        assert self.device.system_info.ustorage is not None
        for disk in self.device.system_info.ustorage.disks:
            if disk.slot == slot:
                self._disk = disk
                self._attr_available = True
                break

        self._attr_is_on = not self._disk.is_healthy

    @callback
    def _async_get_state_attrs(self) -> tuple[Any, ...]:
        """Retrieve data that goes into the current state of the entity.

        Called before and after updating entity and state is only written if there
        is a change.
        """

        return (self._attr_available, self._attr_is_on)


class ProtectEventBinarySensor(EventEntityMixin, BinarySensorEntity):
    """A UniFi Protect Device Binary Sensor for events."""

    entity_description: ProtectBinaryEventEntityDescription

    @callback
    def _async_update_device_from_protect(self, device: ProtectModelWithId) -> None:
        super()._async_update_device_from_protect(device)
        is_on = self.entity_description.get_is_on(self.device, self._event)
        self._attr_is_on: bool | None = is_on
        if not is_on:
            self._event = None
            self._attr_extra_state_attributes = {}

    @callback
    def _async_get_state_attrs(self) -> tuple[Any, ...]:
        """Retrieve data that goes into the current state of the entity.

        Called before and after updating entity and state is only written if there
        is a change.
        """

        return (
            self._attr_available,
            self._attr_is_on,
            self._attr_extra_state_attributes,
        )
