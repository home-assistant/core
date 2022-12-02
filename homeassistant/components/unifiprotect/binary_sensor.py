"""This component provides binary sensors for UniFi Protect."""
from __future__ import annotations

from copy import copy
from dataclasses import dataclass
import logging

from pyunifiprotect.data import (
    NVR,
    Camera,
    Light,
    ModelType,
    MountType,
    ProtectAdoptableDeviceModel,
    ProtectModelWithId,
    Sensor,
    SmartDetectAudioType,
    SmartDetectObjectType,
)
from pyunifiprotect.data.nvr import UOSDisk

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import EntityCategory
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


@dataclass
class ProtectBinaryEntityDescription(
    ProtectRequiredKeysMixin, BinarySensorEntityDescription
):
    """Describes UniFi Protect Binary Sensor entity."""


@dataclass
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
        key="smart_face",
        name="Detections: Face",
        icon="mdi:mdi-face",
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_required_field="can_detect_face",
        ufp_value="is_face_detection_on",
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
        name="Detections: Smoke/CO",
        icon="mdi:fire",
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_required_field="can_detect_smoke",
        ufp_value="is_smoke_detection_on",
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

MOTION_SENSORS: tuple[ProtectBinaryEventEntityDescription, ...] = (
    ProtectBinaryEventEntityDescription(
        key="motion",
        name="Motion",
        device_class=BinarySensorDeviceClass.MOTION,
        ufp_value="is_motion_detected",
        ufp_event_obj="last_motion_event",
    ),
    ProtectBinaryEventEntityDescription(
        key="smart_obj_any",
        name="Object Detected",
        icon="mdi:eye",
        ufp_value="is_smart_detected",
        ufp_required_field="feature_flags.has_smart_detect",
        ufp_event_obj="last_smart_detect_event",
    ),
    ProtectBinaryEventEntityDescription(
        key="smart_obj_person",
        name="Person Detected",
        icon="mdi:walk",
        ufp_value="is_smart_detected",
        ufp_required_field="can_detect_person",
        ufp_enabled="is_person_detection_on",
        ufp_event_obj="last_smart_detect_event",
        ufp_smart_type=SmartDetectObjectType.PERSON,
    ),
    ProtectBinaryEventEntityDescription(
        key="smart_obj_vehicle",
        name="Vehicle Detected",
        icon="mdi:car",
        ufp_value="is_smart_detected",
        ufp_required_field="can_detect_vehicle",
        ufp_enabled="is_vehicle_detection_on",
        ufp_event_obj="last_smart_detect_event",
        ufp_smart_type=SmartDetectObjectType.VEHICLE,
    ),
    ProtectBinaryEventEntityDescription(
        key="smart_obj_face",
        name="Face Detected",
        icon="mdi:mdi-face",
        ufp_value="is_smart_detected",
        ufp_required_field="can_detect_face",
        ufp_enabled="is_face_detection_on",
        ufp_event_obj="last_smart_detect_event",
        ufp_smart_type=SmartDetectObjectType.FACE,
    ),
    ProtectBinaryEventEntityDescription(
        key="smart_obj_package",
        name="Package Detected",
        icon="mdi:package-variant-closed",
        ufp_value="is_smart_detected",
        ufp_required_field="can_detect_package",
        ufp_enabled="is_package_detection_on",
        ufp_event_obj="last_smart_detect_event",
        ufp_smart_type=SmartDetectObjectType.PACKAGE,
    ),
    ProtectBinaryEventEntityDescription(
        key="smart_audio_any",
        name="Audio Object Detected",
        icon="mdi:eye",
        ufp_value="is_smart_detected",
        ufp_required_field="feature_flags.has_smart_detect",
        ufp_event_obj="last_smart_audio_detect_event",
    ),
    ProtectBinaryEventEntityDescription(
        key="smart_audio_smoke",
        name="Smoke Alarm Detected",
        icon="mdi:fire",
        ufp_value="is_smart_detected",
        ufp_required_field="can_detect_smoke",
        ufp_enabled="is_smoke_detection_on",
        ufp_event_obj="last_smart_audio_detect_event",
        ufp_smart_type=SmartDetectAudioType.SMOKE,
    ),
    ProtectBinaryEventEntityDescription(
        key="smart_audio_cmonx",
        name="CO Alarm Detected",
        icon="mdi:fire",
        ufp_value="is_smart_detected",
        ufp_required_field="can_detect_smoke",
        ufp_enabled="is_smoke_detection_on",
        ufp_event_obj="last_smart_audio_detect_event",
        ufp_smart_type=SmartDetectAudioType.CMONX,
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
            entities += _async_motion_entities(data, ufp_device=device)
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
    entities += _async_motion_entities(data)
    entities += _async_nvr_entities(data)

    async_add_entities(entities)


@callback
def _async_motion_entities(
    data: ProtectData,
    ufp_device: ProtectAdoptableDeviceModel | None = None,
) -> list[ProtectDeviceEntity]:
    entities: list[ProtectDeviceEntity] = []
    devices = (
        data.get_by_types({ModelType.CAMERA}) if ufp_device is None else [ufp_device]
    )
    for device in devices:
        for description in MOTION_SENSORS:
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

        self._attr_is_on = self.entity_description.get_ufp_value(self.device)
        # UP Sense can be any of the 3 contact sensor device classes
        if self.entity_description.key == _KEY_DOOR and isinstance(self.device, Sensor):
            self.entity_description.device_class = MOUNT_DEVICE_CLASS_MAP.get(
                self.device.mount_type, BinarySensorDeviceClass.DOOR
            )


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

        description = copy(description)
        description.key = f"{description.key}_{index}"
        description.name = f"{disk.type} {disk.slot}"
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


class ProtectEventBinarySensor(EventEntityMixin, BinarySensorEntity):
    """A UniFi Protect Device Binary Sensor for events."""

    entity_description: ProtectBinaryEventEntityDescription

    @callback
    def _async_update_device_from_protect(self, device: ProtectModelWithId) -> None:
        super()._async_update_device_from_protect(device)
        is_on = self.entity_description.get_is_on(device)
        self._attr_is_on: bool | None = is_on
        if not is_on:
            self._event = None
            self._attr_extra_state_attributes = {}
