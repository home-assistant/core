"""This component provides sensors for UniFi Protect."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import logging
from typing import Any, cast

from pyunifiprotect.data import (
    NVR,
    Camera,
    Event,
    Light,
    ModelType,
    ProtectAdoptableDeviceModel,
    ProtectDeviceModel,
    ProtectModelWithId,
    Sensor,
)

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    DATA_BYTES,
    DATA_RATE_BYTES_PER_SECOND,
    DATA_RATE_MEGABITS_PER_SECOND,
    ELECTRIC_POTENTIAL_VOLT,
    LIGHT_LUX,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    TEMP_CELSIUS,
    TIME_SECONDS,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DISPATCH_ADOPT, DOMAIN
from .data import ProtectData
from .entity import (
    EventThumbnailMixin,
    ProtectDeviceEntity,
    ProtectNVREntity,
    async_all_device_entities,
)
from .models import PermRequired, ProtectRequiredKeysMixin, T
from .utils import async_dispatch_id as _ufpd, async_get_light_motion_current

_LOGGER = logging.getLogger(__name__)
OBJECT_TYPE_NONE = "none"
DEVICE_CLASS_DETECTION = "unifiprotect__detection"


@dataclass
class ProtectSensorEntityDescription(
    ProtectRequiredKeysMixin[T], SensorEntityDescription
):
    """Describes UniFi Protect Sensor entity."""

    precision: int | None = None

    def get_ufp_value(self, obj: T) -> Any:
        """Return value from UniFi Protect device."""
        value = super().get_ufp_value(obj)

        if isinstance(value, float) and self.precision:
            value = round(value, self.precision)
        return value


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
        name="Bluetooth Signal Strength",
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
        name="Link Speed",
        native_unit_of_measurement=DATA_RATE_MEGABITS_PER_SECOND,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        ufp_value="wired_connection_state.phy_rate",
        ufp_required_field="wired_connection_state.phy_rate",
    ),
    ProtectSensorEntityDescription(
        key="wifi_signal",
        name="WiFi Signal Strength",
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
        name="Oldest Recording",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        ufp_value="stats.video.recording_start",
    ),
    ProtectSensorEntityDescription(
        key="storage_used",
        name="Storage Used",
        native_unit_of_measurement=DATA_BYTES,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        ufp_value="stats.storage.used",
    ),
    ProtectSensorEntityDescription(
        key="write_rate",
        name="Disk Write Rate",
        native_unit_of_measurement=DATA_RATE_BYTES_PER_SECOND,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        ufp_value="stats.storage.rate_per_second",
        precision=2,
    ),
    ProtectSensorEntityDescription(
        key="voltage",
        name="Voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        ufp_value="voltage",
        # no feature flag, but voltage will be null if device does not have voltage sensor
        # (i.e. is not G4 Doorbell or not on 1.20.1+)
        ufp_required_field="voltage",
        precision=2,
    ),
    ProtectSensorEntityDescription(
        key="doorbell_last_trip_time",
        name="Last Doorbell Ring",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:doorbell-video",
        ufp_required_field="feature_flags.has_chime",
        ufp_value="last_ring",
        entity_registry_enabled_default=False,
    ),
    ProtectSensorEntityDescription(
        key="lens_type",
        name="Lens Type",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:camera-iris",
        ufp_required_field="has_removable_lens",
        ufp_value="feature_flags.lens_type",
    ),
    ProtectSensorEntityDescription(
        key="mic_level",
        name="Microphone Level",
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
        name="Recording Mode",
        icon="mdi:video-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_value="recording_settings.mode",
        ufp_perm=PermRequired.NO_WRITE,
    ),
    ProtectSensorEntityDescription(
        key="infrared",
        name="Infrared Mode",
        icon="mdi:circle-opacity",
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_required_field="feature_flags.has_led_ir",
        ufp_value="isp_settings.ir_led_mode",
        ufp_perm=PermRequired.NO_WRITE,
    ),
    ProtectSensorEntityDescription(
        key="doorbell_text",
        name="Doorbell Text",
        icon="mdi:card-text",
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_required_field="feature_flags.has_lcd_screen",
        ufp_value="lcd_message.text",
        ufp_perm=PermRequired.NO_WRITE,
    ),
    ProtectSensorEntityDescription(
        key="chime_type",
        name="Chime Type",
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
        name="Received Data",
        native_unit_of_measurement=DATA_BYTES,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL_INCREASING,
        ufp_value="stats.rx_bytes",
    ),
    ProtectSensorEntityDescription(
        key="stats_tx",
        name="Transferred Data",
        native_unit_of_measurement=DATA_BYTES,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL_INCREASING,
        ufp_value="stats.tx_bytes",
    ),
)

SENSE_SENSORS: tuple[ProtectSensorEntityDescription, ...] = (
    ProtectSensorEntityDescription(
        key="battery_level",
        name="Battery Level",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        ufp_value="battery_status.percentage",
    ),
    ProtectSensorEntityDescription(
        key="light_level",
        name="Light Level",
        native_unit_of_measurement=LIGHT_LUX,
        device_class=SensorDeviceClass.ILLUMINANCE,
        state_class=SensorStateClass.MEASUREMENT,
        ufp_value="stats.light.value",
        ufp_enabled="is_light_sensor_enabled",
    ),
    ProtectSensorEntityDescription(
        key="humidity_level",
        name="Humidity Level",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        ufp_value="stats.humidity.value",
        ufp_enabled="is_humidity_sensor_enabled",
    ),
    ProtectSensorEntityDescription(
        key="temperature_level",
        name="Temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        ufp_value="stats.temperature.value",
        ufp_enabled="is_temperature_sensor_enabled",
    ),
    ProtectSensorEntityDescription[Sensor](
        key="alarm_sound",
        name="Alarm Sound Detected",
        ufp_value_fn=_get_alarm_sound,
        ufp_enabled="is_alarm_sensor_enabled",
    ),
    ProtectSensorEntityDescription(
        key="door_last_trip_time",
        name="Last Open",
        device_class=SensorDeviceClass.TIMESTAMP,
        ufp_value="open_status_changed_at",
        entity_registry_enabled_default=False,
    ),
    ProtectSensorEntityDescription(
        key="motion_last_trip_time",
        name="Last Motion Detected",
        device_class=SensorDeviceClass.TIMESTAMP,
        ufp_value="motion_detected_at",
        entity_registry_enabled_default=False,
    ),
    ProtectSensorEntityDescription(
        key="tampering_last_trip_time",
        name="Last Tampering Detected",
        device_class=SensorDeviceClass.TIMESTAMP,
        ufp_value="tampering_detected_at",
        entity_registry_enabled_default=False,
    ),
    ProtectSensorEntityDescription(
        key="sensitivity",
        name="Motion Sensitivity",
        icon="mdi:walk",
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_value="motion_settings.sensitivity",
        ufp_perm=PermRequired.NO_WRITE,
    ),
    ProtectSensorEntityDescription(
        key="mount_type",
        name="Mount Type",
        icon="mdi:screwdriver",
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_value="mount_type",
        ufp_perm=PermRequired.NO_WRITE,
    ),
    ProtectSensorEntityDescription(
        key="paired_camera",
        name="Paired Camera",
        icon="mdi:cctv",
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_value="camera.display_name",
        ufp_perm=PermRequired.NO_WRITE,
    ),
)

DOORLOCK_SENSORS: tuple[ProtectSensorEntityDescription, ...] = (
    ProtectSensorEntityDescription(
        key="battery_level",
        name="Battery Level",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        ufp_value="battery_status.percentage",
    ),
    ProtectSensorEntityDescription(
        key="paired_camera",
        name="Paired Camera",
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
        name="Storage Utilization",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:harddisk",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        ufp_value="storage_stats.utilization",
        precision=2,
    ),
    ProtectSensorEntityDescription(
        key="record_rotating",
        name="Type: Timelapse Video",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:server",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        ufp_value="storage_stats.storage_distribution.timelapse_recordings.percentage",
        precision=2,
    ),
    ProtectSensorEntityDescription(
        key="record_timelapse",
        name="Type: Continuous Video",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:server",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        ufp_value="storage_stats.storage_distribution.continuous_recordings.percentage",
        precision=2,
    ),
    ProtectSensorEntityDescription(
        key="record_detections",
        name="Type: Detections Video",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:server",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        ufp_value="storage_stats.storage_distribution.detections_recordings.percentage",
        precision=2,
    ),
    ProtectSensorEntityDescription(
        key="resolution_HD",
        name="Resolution: HD Video",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:cctv",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        ufp_value="storage_stats.storage_distribution.hd_usage.percentage",
        precision=2,
    ),
    ProtectSensorEntityDescription(
        key="resolution_4K",
        name="Resolution: 4K Video",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:cctv",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        ufp_value="storage_stats.storage_distribution.uhd_usage.percentage",
        precision=2,
    ),
    ProtectSensorEntityDescription(
        key="resolution_free",
        name="Resolution: Free Space",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:cctv",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        ufp_value="storage_stats.storage_distribution.free.percentage",
        precision=2,
    ),
    ProtectSensorEntityDescription[NVR](
        key="record_capacity",
        name="Recording Capacity",
        native_unit_of_measurement=TIME_SECONDS,
        icon="mdi:record-rec",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        ufp_value_fn=_get_nvr_recording_capacity,
    ),
)

NVR_DISABLED_SENSORS: tuple[ProtectSensorEntityDescription, ...] = (
    ProtectSensorEntityDescription(
        key="cpu_utilization",
        name="CPU Utilization",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:speedometer",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        ufp_value="system_info.cpu.average_load",
    ),
    ProtectSensorEntityDescription(
        key="cpu_temperature",
        name="CPU Temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        ufp_value="system_info.cpu.temperature",
    ),
    ProtectSensorEntityDescription[NVR](
        key="memory_utilization",
        name="Memory Utilization",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:memory",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        ufp_value_fn=_get_nvr_memory,
        precision=2,
    ),
)

MOTION_SENSORS: tuple[ProtectSensorEntityDescription, ...] = (
    ProtectSensorEntityDescription(
        key="detected_object",
        name="Detected Object",
        device_class=DEVICE_CLASS_DETECTION,
    ),
)


LIGHT_SENSORS: tuple[ProtectSensorEntityDescription, ...] = (
    ProtectSensorEntityDescription(
        key="motion_last_trip_time",
        name="Last Motion Detected",
        device_class=SensorDeviceClass.TIMESTAMP,
        ufp_value="last_motion",
        entity_registry_enabled_default=False,
    ),
    ProtectSensorEntityDescription(
        key="sensitivity",
        name="Motion Sensitivity",
        icon="mdi:walk",
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_value="light_device_settings.pir_sensitivity",
        ufp_perm=PermRequired.NO_WRITE,
    ),
    ProtectSensorEntityDescription[Light](
        key="light_motion",
        name="Light Mode",
        icon="mdi:spotlight",
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_value_fn=async_get_light_motion_current,
        ufp_perm=PermRequired.NO_WRITE,
    ),
    ProtectSensorEntityDescription(
        key="paired_camera",
        name="Paired Camera",
        icon="mdi:cctv",
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_value="camera.display_name",
        ufp_perm=PermRequired.NO_WRITE,
    ),
)

MOTION_TRIP_SENSORS: tuple[ProtectSensorEntityDescription, ...] = (
    ProtectSensorEntityDescription(
        key="motion_last_trip_time",
        name="Last Motion Detected",
        device_class=SensorDeviceClass.TIMESTAMP,
        ufp_value="last_motion",
        entity_registry_enabled_default=False,
    ),
)

CHIME_SENSORS: tuple[ProtectSensorEntityDescription, ...] = (
    ProtectSensorEntityDescription(
        key="last_ring",
        name="Last Ring",
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


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors for UniFi Protect integration."""
    data: ProtectData = hass.data[DOMAIN][entry.entry_id]

    async def _add_new_device(device: ProtectAdoptableDeviceModel) -> None:
        entities = async_all_device_entities(
            data,
            ProtectDeviceSensor,
            all_descs=ALL_DEVICES_SENSORS,
            camera_descs=CAMERA_SENSORS + CAMERA_DISABLED_SENSORS,
            sense_descs=SENSE_SENSORS,
            light_descs=LIGHT_SENSORS,
            lock_descs=DOORLOCK_SENSORS,
            chime_descs=CHIME_SENSORS,
            viewer_descs=VIEWER_SENSORS,
            ufp_device=device,
        )
        if device.is_adopted_by_us and isinstance(device, Camera):
            entities += _async_motion_entities(data, ufp_device=device)
        async_add_entities(entities)

    entry.async_on_unload(
        async_dispatcher_connect(hass, _ufpd(entry, DISPATCH_ADOPT), _add_new_device)
    )

    entities: list[ProtectDeviceEntity] = async_all_device_entities(
        data,
        ProtectDeviceSensor,
        all_descs=ALL_DEVICES_SENSORS,
        camera_descs=CAMERA_SENSORS + CAMERA_DISABLED_SENSORS,
        sense_descs=SENSE_SENSORS,
        light_descs=LIGHT_SENSORS,
        lock_descs=DOORLOCK_SENSORS,
        chime_descs=CHIME_SENSORS,
        viewer_descs=VIEWER_SENSORS,
    )
    entities += _async_motion_entities(data)
    entities += _async_nvr_entities(data)

    async_add_entities(entities)


@callback
def _async_motion_entities(
    data: ProtectData,
    ufp_device: Camera | None = None,
) -> list[ProtectDeviceEntity]:
    entities: list[ProtectDeviceEntity] = []
    devices = (
        data.get_by_types({ModelType.CAMERA}) if ufp_device is None else [ufp_device]
    )
    for device in devices:
        device = cast(Camera, device)
        for description in MOTION_TRIP_SENSORS:
            entities.append(ProtectDeviceSensor(data, device, description))
            _LOGGER.debug(
                "Adding trip sensor entity %s for %s",
                description.name,
                device.display_name,
            )

        if not device.feature_flags.has_smart_detect:
            continue

        for description in MOTION_SENSORS:
            entities.append(ProtectEventSensor(data, device, description))
            _LOGGER.debug(
                "Adding sensor entity %s for %s",
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
    for description in NVR_SENSORS + NVR_DISABLED_SENSORS:
        entities.append(ProtectNVRSensor(data, device, description))
        _LOGGER.debug("Adding NVR sensor entity %s", description.name)

    return entities


class ProtectDeviceSensor(ProtectDeviceEntity, SensorEntity):
    """A Ubiquiti UniFi Protect Sensor."""

    entity_description: ProtectSensorEntityDescription

    def __init__(
        self,
        data: ProtectData,
        device: ProtectAdoptableDeviceModel,
        description: ProtectSensorEntityDescription,
    ) -> None:
        """Initialize an UniFi Protect sensor."""
        super().__init__(data, device, description)

    @callback
    def _async_update_device_from_protect(self, device: ProtectModelWithId) -> None:
        super()._async_update_device_from_protect(device)
        self._attr_native_value = self.entity_description.get_ufp_value(self.device)


class ProtectNVRSensor(ProtectNVREntity, SensorEntity):
    """A Ubiquiti UniFi Protect Sensor."""

    entity_description: ProtectSensorEntityDescription

    def __init__(
        self,
        data: ProtectData,
        device: NVR,
        description: ProtectSensorEntityDescription,
    ) -> None:
        """Initialize an UniFi Protect sensor."""
        super().__init__(data, device, description)

    @callback
    def _async_update_device_from_protect(self, device: ProtectModelWithId) -> None:
        super()._async_update_device_from_protect(device)
        self._attr_native_value = self.entity_description.get_ufp_value(self.device)


class ProtectEventSensor(ProtectDeviceSensor, EventThumbnailMixin):
    """A UniFi Protect Device Sensor with access tokens."""

    device: Camera

    @callback
    def _async_get_event(self) -> Event | None:
        """Get event from Protect device."""

        event: Event | None = None
        if (
            self.device.is_smart_detected
            and self.device.last_smart_detect_event is not None
            and len(self.device.last_smart_detect_event.smart_detect_types) > 0
        ):
            event = self.device.last_smart_detect_event

        return event

    @callback
    def _async_update_device_from_protect(self, device: ProtectModelWithId) -> None:
        # do not call ProtectDeviceSensor method since we want event to get value here
        EventThumbnailMixin._async_update_device_from_protect(self, device)
        if self._event is None:
            self._attr_native_value = OBJECT_TYPE_NONE
        else:
            self._attr_native_value = self._event.smart_detect_types[0].value
