"""Component providing binary sensors for UniFi Protect."""

from __future__ import annotations

from collections.abc import Sequence
import dataclasses

from uiprotect.data import (
    NVR,
    Camera,
    ModelType,
    MountType,
    ProtectAdoptableDeviceModel,
    Sensor,
    SmartDetectObjectType,
)
from uiprotect.data.nvr import UOSDisk

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .data import ProtectData, ProtectDeviceType, UFPConfigEntry
from .entity import (
    BaseProtectEntity,
    EventEntityMixin,
    PermRequired,
    ProtectDeviceEntity,
    ProtectEntityDescription,
    ProtectEventMixin,
    ProtectIsOnEntity,
    ProtectNVREntity,
    async_all_device_entities,
)

_KEY_DOOR = "door"


@dataclasses.dataclass(frozen=True, kw_only=True)
class ProtectBinaryEntityDescription(
    ProtectEntityDescription, BinarySensorEntityDescription
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
        name="Is dark",
        icon="mdi:brightness-6",
        ufp_value="is_dark",
    ),
    ProtectBinaryEntityDescription(
        key="ssh",
        name="SSH enabled",
        icon="mdi:lock",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_value="is_ssh_enabled",
        ufp_perm=PermRequired.NO_WRITE,
    ),
    ProtectBinaryEntityDescription(
        key="status_light",
        name="Status light on",
        icon="mdi:led-on",
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_required_field="feature_flags.has_led_status",
        ufp_value="led_settings.is_enabled",
        ufp_perm=PermRequired.NO_WRITE,
    ),
    ProtectBinaryEntityDescription(
        key="hdr_mode",
        name="HDR mode",
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
        name="System sounds",
        icon="mdi:speaker",
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_required_field="has_speaker",
        ufp_value="speaker_settings.are_system_sounds_enabled",
        ufp_enabled="feature_flags.has_speaker",
        ufp_perm=PermRequired.NO_WRITE,
    ),
    ProtectBinaryEntityDescription(
        key="osd_name",
        name="Overlay: show name",
        icon="mdi:fullscreen",
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_value="osd_settings.is_name_enabled",
        ufp_perm=PermRequired.NO_WRITE,
    ),
    ProtectBinaryEntityDescription(
        key="osd_date",
        name="Overlay: show date",
        icon="mdi:fullscreen",
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_value="osd_settings.is_date_enabled",
        ufp_perm=PermRequired.NO_WRITE,
    ),
    ProtectBinaryEntityDescription(
        key="osd_logo",
        name="Overlay: show logo",
        icon="mdi:fullscreen",
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_value="osd_settings.is_logo_enabled",
        ufp_perm=PermRequired.NO_WRITE,
    ),
    ProtectBinaryEntityDescription(
        key="osd_bitrate",
        name="Overlay: show bitrate",
        icon="mdi:fullscreen",
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_value="osd_settings.is_debug_enabled",
        ufp_perm=PermRequired.NO_WRITE,
    ),
    ProtectBinaryEntityDescription(
        key="motion_enabled",
        name="Detections: motion",
        icon="mdi:run-fast",
        ufp_value="recording_settings.enable_motion_detection",
        ufp_perm=PermRequired.NO_WRITE,
    ),
    ProtectBinaryEntityDescription(
        key="smart_person",
        name="Detections: person",
        icon="mdi:walk",
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_required_field="can_detect_person",
        ufp_value="is_person_detection_on",
        ufp_perm=PermRequired.NO_WRITE,
    ),
    ProtectBinaryEntityDescription(
        key="smart_vehicle",
        name="Detections: vehicle",
        icon="mdi:car",
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_required_field="can_detect_vehicle",
        ufp_value="is_vehicle_detection_on",
        ufp_perm=PermRequired.NO_WRITE,
    ),
    ProtectBinaryEntityDescription(
        key="smart_animal",
        name="Detections: animal",
        icon="mdi:paw",
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_required_field="can_detect_animal",
        ufp_value="is_animal_detection_on",
        ufp_perm=PermRequired.NO_WRITE,
    ),
    ProtectBinaryEntityDescription(
        key="smart_package",
        name="Detections: package",
        icon="mdi:package-variant-closed",
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_required_field="can_detect_package",
        ufp_value="is_package_detection_on",
        ufp_perm=PermRequired.NO_WRITE,
    ),
    ProtectBinaryEntityDescription(
        key="smart_licenseplate",
        name="Detections: license plate",
        icon="mdi:car",
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_required_field="can_detect_license_plate",
        ufp_value="is_license_plate_detection_on",
        ufp_perm=PermRequired.NO_WRITE,
    ),
    ProtectBinaryEntityDescription(
        key="smart_smoke",
        name="Detections: smoke",
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
        name="Detections: siren",
        icon="mdi:alarm-bell",
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_required_field="can_detect_siren",
        ufp_value="is_siren_detection_on",
        ufp_perm=PermRequired.NO_WRITE,
    ),
    ProtectBinaryEntityDescription(
        key="smart_baby_cry",
        name="Detections: baby cry",
        icon="mdi:cradle",
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_required_field="can_detect_baby_cry",
        ufp_value="is_baby_cry_detection_on",
        ufp_perm=PermRequired.NO_WRITE,
    ),
    ProtectBinaryEntityDescription(
        key="smart_speak",
        name="Detections: speaking",
        icon="mdi:account-voice",
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_required_field="can_detect_speaking",
        ufp_value="is_speaking_detection_on",
        ufp_perm=PermRequired.NO_WRITE,
    ),
    ProtectBinaryEntityDescription(
        key="smart_bark",
        name="Detections: barking",
        icon="mdi:dog",
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_required_field="can_detect_bark",
        ufp_value="is_bark_detection_on",
        ufp_perm=PermRequired.NO_WRITE,
    ),
    ProtectBinaryEntityDescription(
        key="smart_car_alarm",
        name="Detections: car alarm",
        icon="mdi:car",
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_required_field="can_detect_car_alarm",
        ufp_value="is_car_alarm_detection_on",
        ufp_perm=PermRequired.NO_WRITE,
    ),
    ProtectBinaryEntityDescription(
        key="smart_car_horn",
        name="Detections: car horn",
        icon="mdi:bugle",
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_required_field="can_detect_car_horn",
        ufp_value="is_car_horn_detection_on",
        ufp_perm=PermRequired.NO_WRITE,
    ),
    ProtectBinaryEntityDescription(
        key="smart_glass_break",
        name="Detections: glass break",
        icon="mdi:glass-fragile",
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_required_field="can_detect_glass_break",
        ufp_value="is_glass_break_detection_on",
        ufp_perm=PermRequired.NO_WRITE,
    ),
    ProtectBinaryEntityDescription(
        key="track_person",
        name="Tracking: person",
        icon="mdi:walk",
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_required_field="feature_flags.is_ptz",
        ufp_value="is_person_tracking_enabled",
        ufp_perm=PermRequired.NO_WRITE,
    ),
)

LIGHT_SENSORS: tuple[ProtectBinaryEntityDescription, ...] = (
    ProtectBinaryEntityDescription(
        key="dark",
        name="Is dark",
        icon="mdi:brightness-6",
        ufp_value="is_dark",
    ),
    ProtectBinaryEntityDescription(
        key="motion",
        name="Motion detected",
        device_class=BinarySensorDeviceClass.MOTION,
        ufp_value="is_pir_motion_detected",
    ),
    ProtectBinaryEntityDescription(
        key="light",
        name="Flood light",
        icon="mdi:spotlight-beam",
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_value="is_light_on",
        ufp_perm=PermRequired.NO_WRITE,
    ),
    ProtectBinaryEntityDescription(
        key="ssh",
        name="SSH enabled",
        icon="mdi:lock",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_value="is_ssh_enabled",
        ufp_perm=PermRequired.NO_WRITE,
    ),
    ProtectBinaryEntityDescription(
        key="status_light",
        name="Status light on",
        icon="mdi:led-on",
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_value="light_device_settings.is_indicator_enabled",
        ufp_perm=PermRequired.NO_WRITE,
    ),
)

# The mountable sensors can be remounted at run-time which
# means they can change their device class at run-time.
MOUNTABLE_SENSE_SENSORS: tuple[ProtectBinaryEntityDescription, ...] = (
    ProtectBinaryEntityDescription(
        key=_KEY_DOOR,
        name="Contact",
        device_class=BinarySensorDeviceClass.DOOR,
        ufp_value="is_opened",
        ufp_enabled="is_contact_sensor_enabled",
    ),
)

SENSE_SENSORS: tuple[ProtectBinaryEntityDescription, ...] = (
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
        name="Motion detected",
        device_class=BinarySensorDeviceClass.MOTION,
        ufp_value="is_motion_detected",
        ufp_enabled="is_motion_sensor_enabled",
    ),
    ProtectBinaryEntityDescription(
        key="tampering",
        name="Tampering detected",
        device_class=BinarySensorDeviceClass.TAMPER,
        ufp_value="is_tampering_detected",
    ),
    ProtectBinaryEntityDescription(
        key="status_light",
        name="Status light on",
        icon="mdi:led-on",
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_value="led_settings.is_enabled",
        ufp_perm=PermRequired.NO_WRITE,
    ),
    ProtectBinaryEntityDescription(
        key="motion_enabled",
        name="Motion detection",
        icon="mdi:walk",
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_value="motion_settings.is_enabled",
        ufp_perm=PermRequired.NO_WRITE,
    ),
    ProtectBinaryEntityDescription(
        key="temperature",
        name="Temperature sensor",
        icon="mdi:thermometer",
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_value="temperature_settings.is_enabled",
        ufp_perm=PermRequired.NO_WRITE,
    ),
    ProtectBinaryEntityDescription(
        key="humidity",
        name="Humidity sensor",
        icon="mdi:water-percent",
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_value="humidity_settings.is_enabled",
        ufp_perm=PermRequired.NO_WRITE,
    ),
    ProtectBinaryEntityDescription(
        key="light",
        name="Light sensor",
        icon="mdi:brightness-5",
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_value="light_settings.is_enabled",
        ufp_perm=PermRequired.NO_WRITE,
    ),
    ProtectBinaryEntityDescription(
        key="alarm",
        name="Alarm sound detection",
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
        ufp_event_obj="last_ring_event",
    ),
    ProtectBinaryEventEntityDescription(
        key="motion",
        name="Motion",
        device_class=BinarySensorDeviceClass.MOTION,
        ufp_enabled="is_motion_detection_on",
        ufp_event_obj="last_motion_event",
    ),
    ProtectBinaryEventEntityDescription(
        key="smart_obj_any",
        name="Object detected",
        icon="mdi:eye",
        ufp_required_field="feature_flags.has_smart_detect",
        ufp_event_obj="last_smart_detect_event",
        entity_registry_enabled_default=False,
    ),
    ProtectBinaryEventEntityDescription(
        key="smart_obj_person",
        name="Person detected",
        icon="mdi:walk",
        ufp_obj_type=SmartDetectObjectType.PERSON,
        ufp_required_field="can_detect_person",
        ufp_enabled="is_person_detection_on",
        ufp_event_obj="last_person_detect_event",
    ),
    ProtectBinaryEventEntityDescription(
        key="smart_obj_vehicle",
        name="Vehicle detected",
        icon="mdi:car",
        ufp_obj_type=SmartDetectObjectType.VEHICLE,
        ufp_required_field="can_detect_vehicle",
        ufp_enabled="is_vehicle_detection_on",
        ufp_event_obj="last_vehicle_detect_event",
    ),
    ProtectBinaryEventEntityDescription(
        key="smart_obj_animal",
        name="Animal detected",
        icon="mdi:paw",
        ufp_obj_type=SmartDetectObjectType.ANIMAL,
        ufp_required_field="can_detect_animal",
        ufp_enabled="is_animal_detection_on",
        ufp_event_obj="last_animal_detect_event",
    ),
    ProtectBinaryEventEntityDescription(
        key="smart_obj_package",
        name="Package detected",
        icon="mdi:package-variant-closed",
        entity_registry_enabled_default=False,
        ufp_obj_type=SmartDetectObjectType.PACKAGE,
        ufp_required_field="can_detect_package",
        ufp_enabled="is_package_detection_on",
        ufp_event_obj="last_package_detect_event",
    ),
    ProtectBinaryEventEntityDescription(
        key="smart_audio_any",
        name="Audio object detected",
        icon="mdi:eye",
        ufp_required_field="feature_flags.has_smart_detect",
        ufp_event_obj="last_smart_audio_detect_event",
        entity_registry_enabled_default=False,
    ),
    ProtectBinaryEventEntityDescription(
        key="smart_audio_smoke",
        name="Smoke alarm detected",
        icon="mdi:fire",
        ufp_obj_type=SmartDetectObjectType.SMOKE,
        ufp_required_field="can_detect_smoke",
        ufp_enabled="is_smoke_detection_on",
        ufp_event_obj="last_smoke_detect_event",
    ),
    ProtectBinaryEventEntityDescription(
        key="smart_audio_cmonx",
        name="CO alarm detected",
        icon="mdi:molecule-co",
        ufp_required_field="can_detect_co",
        ufp_enabled="is_co_detection_on",
        ufp_event_obj="last_cmonx_detect_event",
        ufp_obj_type=SmartDetectObjectType.CMONX,
    ),
    ProtectBinaryEventEntityDescription(
        key="smart_audio_siren",
        name="Siren detected",
        icon="mdi:alarm-bell",
        ufp_obj_type=SmartDetectObjectType.SIREN,
        ufp_required_field="can_detect_siren",
        ufp_enabled="is_siren_detection_on",
        ufp_event_obj="last_siren_detect_event",
    ),
    ProtectBinaryEventEntityDescription(
        key="smart_audio_baby_cry",
        name="Baby cry detected",
        icon="mdi:cradle",
        ufp_obj_type=SmartDetectObjectType.BABY_CRY,
        ufp_required_field="can_detect_baby_cry",
        ufp_enabled="is_baby_cry_detection_on",
        ufp_event_obj="last_baby_cry_detect_event",
    ),
    ProtectBinaryEventEntityDescription(
        key="smart_audio_speak",
        name="Speaking detected",
        icon="mdi:account-voice",
        ufp_obj_type=SmartDetectObjectType.SPEAK,
        ufp_required_field="can_detect_speaking",
        ufp_enabled="is_speaking_detection_on",
        ufp_event_obj="last_speaking_detect_event",
    ),
    ProtectBinaryEventEntityDescription(
        key="smart_audio_bark",
        name="Barking detected",
        icon="mdi:dog",
        ufp_obj_type=SmartDetectObjectType.BARK,
        ufp_required_field="can_detect_bark",
        ufp_enabled="is_bark_detection_on",
        ufp_event_obj="last_bark_detect_event",
    ),
    ProtectBinaryEventEntityDescription(
        key="smart_audio_car_alarm",
        name="Car alarm detected",
        icon="mdi:car",
        ufp_obj_type=SmartDetectObjectType.BURGLAR,
        ufp_required_field="can_detect_car_alarm",
        ufp_enabled="is_car_alarm_detection_on",
        ufp_event_obj="last_car_alarm_detect_event",
    ),
    ProtectBinaryEventEntityDescription(
        key="smart_audio_car_horn",
        name="Car horn detected",
        icon="mdi:bugle",
        ufp_obj_type=SmartDetectObjectType.CAR_HORN,
        ufp_required_field="can_detect_car_horn",
        ufp_enabled="is_car_horn_detection_on",
        ufp_event_obj="last_car_horn_detect_event",
    ),
    ProtectBinaryEventEntityDescription(
        key="smart_audio_glass_break",
        name="Glass break detected",
        icon="mdi:glass-fragile",
        ufp_obj_type=SmartDetectObjectType.GLASS_BREAK,
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
        name="Status light on",
        icon="mdi:led-on",
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_value="led_settings.is_enabled",
        ufp_perm=PermRequired.NO_WRITE,
    ),
)

VIEWER_SENSORS: tuple[ProtectBinaryEntityDescription, ...] = (
    ProtectBinaryEntityDescription(
        key="ssh",
        name="SSH enabled",
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

_MODEL_DESCRIPTIONS: dict[ModelType, Sequence[ProtectEntityDescription]] = {
    ModelType.CAMERA: CAMERA_SENSORS,
    ModelType.LIGHT: LIGHT_SENSORS,
    ModelType.SENSOR: SENSE_SENSORS,
    ModelType.DOORLOCK: DOORLOCK_SENSORS,
    ModelType.VIEWPORT: VIEWER_SENSORS,
}

_MOUNTABLE_MODEL_DESCRIPTIONS: dict[ModelType, Sequence[ProtectEntityDescription]] = {
    ModelType.SENSOR: MOUNTABLE_SENSE_SENSORS,
}


class ProtectDeviceBinarySensor(
    ProtectIsOnEntity, ProtectDeviceEntity, BinarySensorEntity
):
    """A UniFi Protect Device Binary Sensor."""

    entity_description: ProtectBinaryEntityDescription


class MountableProtectDeviceBinarySensor(ProtectDeviceBinarySensor):
    """A UniFi Protect Device Binary Sensor that can change device class at runtime."""

    device: Sensor
    _state_attrs = ("_attr_available", "_attr_is_on", "_attr_device_class")

    @callback
    def _async_update_device_from_protect(self, device: ProtectDeviceType) -> None:
        super()._async_update_device_from_protect(device)
        # UP Sense can be any of the 3 contact sensor device classes
        self._attr_device_class = MOUNT_DEVICE_CLASS_MAP.get(
            self.device.mount_type, BinarySensorDeviceClass.DOOR
        )


class ProtectDiskBinarySensor(ProtectNVREntity, BinarySensorEntity):
    """A UniFi Protect NVR Disk Binary Sensor."""

    _disk: UOSDisk
    entity_description: ProtectBinaryEntityDescription
    _state_attrs = ("_attr_available", "_attr_is_on")

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
    def _async_update_device_from_protect(self, device: ProtectDeviceType) -> None:
        super()._async_update_device_from_protect(device)
        slot = self._disk.slot
        self._attr_available = False
        available = self.data.last_update_success

        # should not be possible since it would require user to
        # _downgrade_ to make ustorage disppear
        assert self.device.system_info.ustorage is not None
        for disk in self.device.system_info.ustorage.disks:
            if disk.slot == slot:
                self._disk = disk
                self._attr_available = available
                break

        self._attr_is_on = not self._disk.is_healthy


class ProtectEventBinarySensor(EventEntityMixin, BinarySensorEntity):
    """A UniFi Protect Device Binary Sensor for events."""

    entity_description: ProtectBinaryEventEntityDescription
    _state_attrs = ("_attr_available", "_attr_is_on", "_attr_extra_state_attributes")

    @callback
    def _set_event_done(self) -> None:
        self._attr_is_on = False
        self._attr_extra_state_attributes = {}

    @callback
    def _async_update_device_from_protect(self, device: ProtectDeviceType) -> None:
        description = self.entity_description

        prev_event = self._event
        prev_event_end = self._event_end
        super()._async_update_device_from_protect(device)
        if event := description.get_event_obj(device):
            self._event = event
            self._event_end = event.end if event else None

        if not (
            event
            and (
                description.ufp_obj_type is None
                or description.has_matching_smart(event)
            )
            and not self._event_already_ended(prev_event, prev_event_end)
        ):
            self._set_event_done()
            return

        self._attr_is_on = True
        self._set_event_attrs(event)
        if event.end:
            self._async_event_with_immediate_end()


MODEL_DESCRIPTIONS_WITH_CLASS = (
    (_MODEL_DESCRIPTIONS, ProtectDeviceBinarySensor),
    (_MOUNTABLE_MODEL_DESCRIPTIONS, MountableProtectDeviceBinarySensor),
)


@callback
def _async_event_entities(
    data: ProtectData,
    ufp_device: ProtectAdoptableDeviceModel | None = None,
) -> list[ProtectDeviceEntity]:
    entities: list[ProtectDeviceEntity] = []
    for device in data.get_cameras() if ufp_device is None else [ufp_device]:
        entities.extend(
            ProtectEventBinarySensor(data, device, description)
            for description in EVENT_SENSORS
            if description.has_required(device)
        )
    return entities


@callback
def _async_nvr_entities(
    data: ProtectData,
) -> list[BaseProtectEntity]:
    device = data.api.bootstrap.nvr
    if (ustorage := device.system_info.ustorage) is None:
        return []
    return [
        ProtectDiskBinarySensor(data, device, description, disk)
        for disk in ustorage.disks
        for description in DISK_SENSORS
        if disk.has_disk
    ]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: UFPConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up binary sensors for UniFi Protect integration."""
    data = entry.runtime_data

    @callback
    def _add_new_device(device: ProtectAdoptableDeviceModel) -> None:
        entities: list[BaseProtectEntity] = []
        for model_descriptions, klass in MODEL_DESCRIPTIONS_WITH_CLASS:
            entities += async_all_device_entities(
                data, klass, model_descriptions=model_descriptions, ufp_device=device
            )
        if device.is_adopted and isinstance(device, Camera):
            entities += _async_event_entities(data, ufp_device=device)
        async_add_entities(entities)

    data.async_subscribe_adopt(_add_new_device)
    entities: list[BaseProtectEntity] = []
    for model_descriptions, klass in MODEL_DESCRIPTIONS_WITH_CLASS:
        entities += async_all_device_entities(
            data, klass, model_descriptions=model_descriptions
        )
    entities += _async_event_entities(data)
    entities += _async_nvr_entities(data)
    async_add_entities(entities)
