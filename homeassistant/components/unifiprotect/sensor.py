"""Component providing sensors for UniFi Protect."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from functools import partial
import logging
from typing import Any

from uiprotect.data import (
    NVR,
    Camera,
    Light,
    ModelType,
    ProtectAdoptableDeviceModel,
    ProtectDeviceModel,
    Sensor,
    SmartDetectObjectType,
)

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    LIGHT_LUX,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfDataRate,
    UnitOfElectricPotential,
    UnitOfInformation,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .data import ProtectData, ProtectDeviceType, UFPConfigEntry
from .entity import (
    BaseProtectEntity,
    EventEntityMixin,
    PermRequired,
    ProtectDeviceEntity,
    ProtectEntityDescription,
    ProtectEventMixin,
    ProtectNVREntity,
    T,
    async_all_device_entities,
)
from .utils import async_get_light_motion_current

_LOGGER = logging.getLogger(__name__)
OBJECT_TYPE_NONE = "none"


@dataclass(frozen=True, kw_only=True)
class ProtectSensorEntityDescription(
    ProtectEntityDescription[T], SensorEntityDescription
):
    """Describes UniFi Protect Sensor entity."""

    precision: int | None = None

    def __post_init__(self) -> None:
        """Ensure values are rounded if precision is set."""
        super().__post_init__()
        if precision := self.precision:
            object.__setattr__(
                self,
                "get_ufp_value",
                partial(self._rounded_value, precision, self.get_ufp_value),
            )

    def _rounded_value(self, precision: int, getter: Callable[[T], Any], obj: T) -> Any:
        """Round value to precision if set."""
        return None if (v := getter(obj)) is None else round(v, precision)


@dataclass(frozen=True, kw_only=True)
class ProtectSensorEventEntityDescription(
    ProtectEventMixin[T], SensorEntityDescription
):
    """Describes UniFi Protect Sensor entity."""


def _get_uptime(obj: ProtectDeviceModel) -> datetime | None:
    if obj.up_since is None:
        return None

    # up_since can vary slightly over time
    # truncate to ensure no extra state_change events fire
    return obj.up_since.replace(second=0, microsecond=0)


def _get_nvr_recording_capacity(obj: NVR) -> int:
    if obj.storage_stats.capacity is None:
        return 0

    return int(obj.storage_stats.capacity.total_seconds())


def _get_nvr_memory(obj: NVR) -> float | None:
    memory = obj.system_info.memory
    if memory.available is None or memory.total is None:
        return None
    return (1 - memory.available / memory.total) * 100


def _get_alarm_sound(obj: Sensor) -> str:
    alarm_type = OBJECT_TYPE_NONE
    if (
        obj.is_alarm_detected
        and obj.last_alarm_event is not None
        and obj.last_alarm_event.metadata is not None
    ):
        alarm_type = obj.last_alarm_event.metadata.alarm_type or OBJECT_TYPE_NONE
    return alarm_type.lower()


ALL_DEVICES_SENSORS: tuple[ProtectSensorEntityDescription, ...] = (
    ProtectSensorEntityDescription(
        key="uptime",
        name="Uptime",
        icon="mdi:clock",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        ufp_value_fn=_get_uptime,
    ),
    ProtectSensorEntityDescription(
        key="ble_signal",
        name="Bluetooth signal strength",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        ufp_value="bluetooth_connection_state.signal_strength",
        ufp_required_field="bluetooth_connection_state.signal_strength",
    ),
    ProtectSensorEntityDescription(
        key="phy_rate",
        name="Link speed",
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.MEGABITS_PER_SECOND,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        ufp_value="wired_connection_state.phy_rate",
        ufp_required_field="wired_connection_state.phy_rate",
    ),
    ProtectSensorEntityDescription(
        key="wifi_signal",
        name="WiFi signal strength",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        ufp_value="wifi_connection_state.signal_strength",
        ufp_required_field="wifi_connection_state.signal_strength",
    ),
)

CAMERA_SENSORS: tuple[ProtectSensorEntityDescription, ...] = (
    ProtectSensorEntityDescription(
        key="oldest_recording",
        name="Oldest recording",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        ufp_value="stats.video.recording_start",
    ),
    ProtectSensorEntityDescription(
        key="storage_used",
        name="Storage used",
        native_unit_of_measurement=UnitOfInformation.BYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        ufp_value="stats.storage.used",
        suggested_unit_of_measurement=UnitOfInformation.MEGABYTES,
        suggested_display_precision=2,
    ),
    ProtectSensorEntityDescription(
        key="write_rate",
        name="Disk write rate",
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.BYTES_PER_SECOND,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        ufp_value="stats.storage.rate_per_second",
        precision=2,
        suggested_unit_of_measurement=UnitOfDataRate.MEGABYTES_PER_SECOND,
        suggested_display_precision=2,
    ),
    ProtectSensorEntityDescription(
        key="voltage",
        name="Voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        ufp_value="voltage",
        # no feature flag, but voltage will be null if device does not have
        # voltage sensor (i.e. is not G4 Doorbell or not on 1.20.1+)
        ufp_required_field="voltage",
        precision=2,
    ),
    ProtectSensorEntityDescription(
        key="doorbell_last_trip_time",
        name="Last doorbell ring",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:doorbell-video",
        ufp_required_field="feature_flags.is_doorbell",
        ufp_value="last_ring",
        entity_registry_enabled_default=False,
    ),
    ProtectSensorEntityDescription(
        key="lens_type",
        name="Lens type",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:camera-iris",
        ufp_required_field="has_removable_lens",
        ufp_value="feature_flags.lens_type",
    ),
    ProtectSensorEntityDescription(
        key="mic_level",
        name="Microphone level",
        icon="mdi:microphone",
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_required_field="has_mic",
        ufp_value="mic_volume",
        ufp_enabled="feature_flags.has_mic",
        ufp_perm=PermRequired.NO_WRITE,
    ),
    ProtectSensorEntityDescription(
        key="recording_mode",
        name="Recording mode",
        icon="mdi:video-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_value="recording_settings.mode.value",
        ufp_perm=PermRequired.NO_WRITE,
    ),
    ProtectSensorEntityDescription(
        key="infrared",
        name="Infrared mode",
        icon="mdi:circle-opacity",
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_required_field="feature_flags.has_led_ir",
        ufp_value="isp_settings.ir_led_mode.value",
        ufp_perm=PermRequired.NO_WRITE,
    ),
    ProtectSensorEntityDescription(
        key="doorbell_text",
        name="Doorbell text",
        icon="mdi:card-text",
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_required_field="feature_flags.has_lcd_screen",
        ufp_value="lcd_message.text",
        ufp_perm=PermRequired.NO_WRITE,
    ),
    ProtectSensorEntityDescription(
        key="chime_type",
        name="Chime type",
        icon="mdi:bell",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        ufp_required_field="feature_flags.has_chime",
        ufp_value="chime_type",
    ),
)

CAMERA_DISABLED_SENSORS: tuple[ProtectSensorEntityDescription, ...] = (
    ProtectSensorEntityDescription(
        key="stats_rx",
        name="Received data",
        native_unit_of_measurement=UnitOfInformation.BYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL_INCREASING,
        ufp_value="stats.rx_bytes",
        suggested_unit_of_measurement=UnitOfInformation.MEGABYTES,
        suggested_display_precision=2,
    ),
    ProtectSensorEntityDescription(
        key="stats_tx",
        name="Transferred data",
        native_unit_of_measurement=UnitOfInformation.BYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL_INCREASING,
        ufp_value="stats.tx_bytes",
        suggested_unit_of_measurement=UnitOfInformation.MEGABYTES,
        suggested_display_precision=2,
    ),
)

SENSE_SENSORS: tuple[ProtectSensorEntityDescription, ...] = (
    ProtectSensorEntityDescription(
        key="battery_level",
        name="Battery level",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        ufp_value="battery_status.percentage",
    ),
    ProtectSensorEntityDescription(
        key="light_level",
        name="Light level",
        native_unit_of_measurement=LIGHT_LUX,
        device_class=SensorDeviceClass.ILLUMINANCE,
        state_class=SensorStateClass.MEASUREMENT,
        ufp_value="stats.light.value",
        ufp_enabled="is_light_sensor_enabled",
    ),
    ProtectSensorEntityDescription(
        key="humidity_level",
        name="Humidity level",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        ufp_value="stats.humidity.value",
        ufp_enabled="is_humidity_sensor_enabled",
    ),
    ProtectSensorEntityDescription(
        key="temperature_level",
        name="Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        ufp_value="stats.temperature.value",
        ufp_enabled="is_temperature_sensor_enabled",
    ),
    ProtectSensorEntityDescription[Sensor](
        key="alarm_sound",
        name="Alarm sound detected",
        ufp_value_fn=_get_alarm_sound,
        ufp_enabled="is_alarm_sensor_enabled",
    ),
    ProtectSensorEntityDescription(
        key="door_last_trip_time",
        name="Last open",
        device_class=SensorDeviceClass.TIMESTAMP,
        ufp_value="open_status_changed_at",
        entity_registry_enabled_default=False,
    ),
    ProtectSensorEntityDescription(
        key="motion_last_trip_time",
        name="Last motion detected",
        device_class=SensorDeviceClass.TIMESTAMP,
        ufp_value="motion_detected_at",
        entity_registry_enabled_default=False,
    ),
    ProtectSensorEntityDescription(
        key="tampering_last_trip_time",
        name="Last tampering detected",
        device_class=SensorDeviceClass.TIMESTAMP,
        ufp_value="tampering_detected_at",
        entity_registry_enabled_default=False,
    ),
    ProtectSensorEntityDescription(
        key="sensitivity",
        name="Motion sensitivity",
        icon="mdi:walk",
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_value="motion_settings.sensitivity",
        ufp_perm=PermRequired.NO_WRITE,
    ),
    ProtectSensorEntityDescription(
        key="mount_type",
        name="Mount type",
        icon="mdi:screwdriver",
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_value="mount_type",
        ufp_perm=PermRequired.NO_WRITE,
    ),
    ProtectSensorEntityDescription(
        key="paired_camera",
        name="Paired camera",
        icon="mdi:cctv",
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_value="camera.display_name",
        ufp_perm=PermRequired.NO_WRITE,
    ),
)

DOORLOCK_SENSORS: tuple[ProtectSensorEntityDescription, ...] = (
    ProtectSensorEntityDescription(
        key="battery_level",
        name="Battery level",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        ufp_value="battery_status.percentage",
    ),
    ProtectSensorEntityDescription(
        key="paired_camera",
        name="Paired camera",
        icon="mdi:cctv",
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_value="camera.display_name",
        ufp_perm=PermRequired.NO_WRITE,
    ),
)

NVR_SENSORS: tuple[ProtectSensorEntityDescription, ...] = (
    ProtectSensorEntityDescription(
        key="uptime",
        name="Uptime",
        icon="mdi:clock",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_value_fn=_get_uptime,
    ),
    ProtectSensorEntityDescription(
        key="storage_utilization",
        name="Storage utilization",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:harddisk",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        ufp_value="storage_stats.utilization",
        precision=2,
    ),
    ProtectSensorEntityDescription(
        key="record_rotating",
        name="Type: timelapse video",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:server",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        ufp_value="storage_stats.storage_distribution.timelapse_recordings.percentage",
        precision=2,
    ),
    ProtectSensorEntityDescription(
        key="record_timelapse",
        name="Type: continuous video",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:server",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        ufp_value="storage_stats.storage_distribution.continuous_recordings.percentage",
        precision=2,
    ),
    ProtectSensorEntityDescription(
        key="record_detections",
        name="Type: detections video",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:server",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        ufp_value="storage_stats.storage_distribution.detections_recordings.percentage",
        precision=2,
    ),
    ProtectSensorEntityDescription(
        key="resolution_HD",
        name="Resolution: HD video",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:cctv",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        ufp_value="storage_stats.storage_distribution.hd_usage.percentage",
        precision=2,
    ),
    ProtectSensorEntityDescription(
        key="resolution_4K",
        name="Resolution: 4K video",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:cctv",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        ufp_value="storage_stats.storage_distribution.uhd_usage.percentage",
        precision=2,
    ),
    ProtectSensorEntityDescription(
        key="resolution_free",
        name="Resolution: free space",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:cctv",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        ufp_value="storage_stats.storage_distribution.free.percentage",
        precision=2,
    ),
    ProtectSensorEntityDescription[NVR](
        key="record_capacity",
        name="Recording capacity",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        icon="mdi:record-rec",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        ufp_value_fn=_get_nvr_recording_capacity,
    ),
)

NVR_DISABLED_SENSORS: tuple[ProtectSensorEntityDescription, ...] = (
    ProtectSensorEntityDescription(
        key="cpu_utilization",
        name="CPU utilization",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:speedometer",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        ufp_value="system_info.cpu.average_load",
    ),
    ProtectSensorEntityDescription(
        key="cpu_temperature",
        name="CPU temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        ufp_value="system_info.cpu.temperature",
    ),
    ProtectSensorEntityDescription[NVR](
        key="memory_utilization",
        name="Memory utilization",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:memory",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        ufp_value_fn=_get_nvr_memory,
        precision=2,
    ),
)

LICENSE_PLATE_EVENT_SENSORS: tuple[ProtectSensorEventEntityDescription, ...] = (
    ProtectSensorEventEntityDescription(
        key="smart_obj_licenseplate",
        name="License plate detected",
        icon="mdi:car",
        translation_key="license_plate",
        ufp_obj_type=SmartDetectObjectType.LICENSE_PLATE,
        ufp_required_field="can_detect_license_plate",
        ufp_event_obj="last_license_plate_detect_event",
    ),
)


LIGHT_SENSORS: tuple[ProtectSensorEntityDescription, ...] = (
    ProtectSensorEntityDescription(
        key="motion_last_trip_time",
        name="Last motion detected",
        device_class=SensorDeviceClass.TIMESTAMP,
        ufp_value="last_motion",
        entity_registry_enabled_default=False,
    ),
    ProtectSensorEntityDescription(
        key="sensitivity",
        name="Motion sensitivity",
        icon="mdi:walk",
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_value="light_device_settings.pir_sensitivity",
        ufp_perm=PermRequired.NO_WRITE,
    ),
    ProtectSensorEntityDescription[Light](
        key="light_motion",
        name="Light mode",
        icon="mdi:spotlight",
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_value_fn=async_get_light_motion_current,
        ufp_perm=PermRequired.NO_WRITE,
    ),
    ProtectSensorEntityDescription(
        key="paired_camera",
        name="Paired camera",
        icon="mdi:cctv",
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_value="camera.display_name",
        ufp_perm=PermRequired.NO_WRITE,
    ),
)

MOTION_TRIP_SENSORS: tuple[ProtectSensorEntityDescription, ...] = (
    ProtectSensorEntityDescription(
        key="motion_last_trip_time",
        name="Last motion detected",
        device_class=SensorDeviceClass.TIMESTAMP,
        ufp_value="last_motion",
        entity_registry_enabled_default=False,
    ),
)

CHIME_SENSORS: tuple[ProtectSensorEntityDescription, ...] = (
    ProtectSensorEntityDescription(
        key="last_ring",
        name="Last ring",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:bell",
        ufp_value="last_ring",
    ),
    ProtectSensorEntityDescription(
        key="volume",
        name="Volume",
        icon="mdi:speaker",
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_value="volume",
        ufp_perm=PermRequired.NO_WRITE,
    ),
)

VIEWER_SENSORS: tuple[ProtectSensorEntityDescription, ...] = (
    ProtectSensorEntityDescription(
        key="viewer",
        name="Liveview",
        icon="mdi:view-dashboard",
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_value="liveview.name",
        ufp_perm=PermRequired.NO_WRITE,
    ),
)

_MODEL_DESCRIPTIONS: dict[ModelType, Sequence[ProtectEntityDescription]] = {
    ModelType.CAMERA: CAMERA_SENSORS + CAMERA_DISABLED_SENSORS,
    ModelType.SENSOR: SENSE_SENSORS,
    ModelType.LIGHT: LIGHT_SENSORS,
    ModelType.DOORLOCK: DOORLOCK_SENSORS,
    ModelType.CHIME: CHIME_SENSORS,
    ModelType.VIEWPORT: VIEWER_SENSORS,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: UFPConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors for UniFi Protect integration."""
    data = entry.runtime_data

    @callback
    def _add_new_device(device: ProtectAdoptableDeviceModel) -> None:
        entities = async_all_device_entities(
            data,
            ProtectDeviceSensor,
            all_descs=ALL_DEVICES_SENSORS,
            model_descriptions=_MODEL_DESCRIPTIONS,
            ufp_device=device,
        )
        if device.is_adopted_by_us and isinstance(device, Camera):
            entities += _async_event_entities(data, ufp_device=device)
        async_add_entities(entities)

    data.async_subscribe_adopt(_add_new_device)
    entities = async_all_device_entities(
        data,
        ProtectDeviceSensor,
        all_descs=ALL_DEVICES_SENSORS,
        model_descriptions=_MODEL_DESCRIPTIONS,
    )
    entities += _async_event_entities(data)
    entities += _async_nvr_entities(data)

    async_add_entities(entities)


@callback
def _async_event_entities(
    data: ProtectData,
    ufp_device: Camera | None = None,
) -> list[ProtectDeviceEntity]:
    entities: list[ProtectDeviceEntity] = []
    cameras = data.get_cameras() if ufp_device is None else [ufp_device]
    for camera in cameras:
        for description in MOTION_TRIP_SENSORS:
            entities.append(ProtectDeviceSensor(data, camera, description))
            _LOGGER.debug(
                "Adding trip sensor entity %s for %s",
                description.name,
                camera.display_name,
            )

        if not camera.feature_flags.has_smart_detect:
            continue

        for event_desc in LICENSE_PLATE_EVENT_SENSORS:
            if not event_desc.has_required(camera):
                continue

            entities.append(ProtectLicensePlateEventSensor(data, camera, event_desc))
            _LOGGER.debug(
                "Adding sensor entity %s for %s",
                description.name,
                camera.display_name,
            )

    return entities


@callback
def _async_nvr_entities(
    data: ProtectData,
) -> list[BaseProtectEntity]:
    entities: list[BaseProtectEntity] = []
    device = data.api.bootstrap.nvr
    for description in NVR_SENSORS + NVR_DISABLED_SENSORS:
        entities.append(ProtectNVRSensor(data, device, description))
        _LOGGER.debug("Adding NVR sensor entity %s", description.name)

    return entities


class BaseProtectSensor(BaseProtectEntity, SensorEntity):
    """A UniFi Protect Sensor Entity."""

    entity_description: ProtectSensorEntityDescription
    _state_attrs = ("_attr_available", "_attr_native_value")

    def _async_update_device_from_protect(self, device: ProtectDeviceType) -> None:
        super()._async_update_device_from_protect(device)
        self._attr_native_value = self.entity_description.get_ufp_value(self.device)


class ProtectDeviceSensor(BaseProtectSensor, ProtectDeviceEntity):
    """A Ubiquiti UniFi Protect Sensor."""


class ProtectNVRSensor(BaseProtectSensor, ProtectNVREntity):
    """A Ubiquiti UniFi Protect Sensor."""


class ProtectEventSensor(EventEntityMixin, SensorEntity):
    """A UniFi Protect Device Sensor with access tokens."""

    entity_description: ProtectSensorEventEntityDescription
    _state_attrs = (
        "_attr_available",
        "_attr_native_value",
        "_attr_extra_state_attributes",
    )


class ProtectLicensePlateEventSensor(ProtectEventSensor):
    """A UniFi Protect license plate sensor."""

    device: Camera

    @callback
    def _set_event_done(self) -> None:
        self._attr_native_value = OBJECT_TYPE_NONE
        self._attr_extra_state_attributes = {}

    @callback
    def _async_update_device_from_protect(self, device: ProtectDeviceType) -> None:
        description = self.entity_description

        prev_event = self._event
        prev_event_end = self._event_end
        super()._async_update_device_from_protect(device)
        if event := description.get_event_obj(device):
            self._event = event
            self._event_end = event.end

        if not (
            event
            and (metadata := event.metadata)
            and (license_plate := metadata.license_plate)
            and description.has_matching_smart(event)
            and not self._event_already_ended(prev_event, prev_event_end)
        ):
            self._set_event_done()
            return

        self._attr_native_value = license_plate.name
        self._set_event_attrs(event)
        if event.end:
            self._async_event_with_immediate_end()
