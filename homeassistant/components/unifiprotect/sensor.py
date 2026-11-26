"""Component providing sensors for UniFi Protect."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from functools import partial
import logging
import operator
from typing import Any, cast, override

from uiprotect.data import (
    NVR,
    Fob,
    FobAwayState,
    ModelType,
    ProtectAdoptableDeviceModel,
    Sensor,
)
from uiprotect.data.public_devices import PublicDeviceModel, SensorFeatureCapability

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
    Platform,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .data import ProtectData, ProtectDeviceType, UFPConfigEntry
from .entity import (
    BaseProtectEntity,
    PermRequired,
    ProtectDeviceEntity,
    ProtectEntityDescription,
    ProtectNVREntity,
    T,
    async_all_device_entities,
    async_remove_unsupported_sense_entities,
)

_LOGGER = logging.getLogger(__name__)
OBJECT_TYPE_NONE = "none"
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class ProtectSensorEntityDescription(
    ProtectEntityDescription[T], SensorEntityDescription
):
    """Describes UniFi Protect Sensor entity."""

    precision: int | None = None

    @override
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


def _get_nvr_recording_capacity(obj: NVR) -> int:
    if obj.storage_stats.capacity is None:
        return 0

    return int(obj.storage_stats.capacity.total_seconds())


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
        key="wifi_signal",
        translation_key="wifi_signal_strength",
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
        key="recording_mode",
        translation_key="recording_mode",
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_value="recording_settings.mode.value",
        ufp_perm=PermRequired.NO_WRITE,
    ),
    ProtectSensorEntityDescription(
        key="infrared",
        translation_key="infrared_mode",
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_required_field="feature_flags.has_led_ir",
        ufp_value="isp_settings.ir_led_mode.value",
        ufp_perm=PermRequired.NO_WRITE,
    ),
    ProtectSensorEntityDescription(
        key="chime_type",
        translation_key="chime_type",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        ufp_required_field="feature_flags.has_chime",
        ufp_value="chime_type",
    ),
)

SENSE_SENSORS: tuple[ProtectSensorEntityDescription, ...] = (
    ProtectSensorEntityDescription(
        key="battery_level",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        ufp_public_value="wireless_connection_state.battery_status.percentage",
    ),
    ProtectSensorEntityDescription(
        key="light_level",
        native_unit_of_measurement=LIGHT_LUX,
        device_class=SensorDeviceClass.ILLUMINANCE,
        state_class=SensorStateClass.MEASUREMENT,
        ufp_public_value="stats.light.value",
        ufp_public_enabled_fn=operator.attrgetter("is_light_sensor_enabled"),
        ufp_capability=SensorFeatureCapability.LIGHT,
    ),
    ProtectSensorEntityDescription(
        key="humidity_level",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        ufp_public_value="stats.humidity.value",
        ufp_public_enabled_fn=operator.attrgetter("is_humidity_sensor_enabled"),
        ufp_capability=SensorFeatureCapability.HUMIDITY,
    ),
    ProtectSensorEntityDescription(
        key="temperature_level",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        ufp_public_value="stats.temperature.value",
        ufp_public_enabled_fn=operator.attrgetter("is_temperature_sensor_enabled"),
        ufp_capability=SensorFeatureCapability.TEMPERATURE,
    ),
    ProtectSensorEntityDescription[Sensor](
        key="alarm_sound",
        translation_key="alarm_sound_detected",
        ufp_value_fn=_get_alarm_sound,
        ufp_enabled="is_alarm_sensor_enabled",
        ufp_capability=SensorFeatureCapability.SMOKE,
    ),
    ProtectSensorEntityDescription(
        key="door_last_trip_time",
        translation_key="last_open",
        device_class=SensorDeviceClass.TIMESTAMP,
        ufp_public_value="open_status_changed_at_dt",
        ufp_capability=SensorFeatureCapability.OPEN,
        entity_registry_enabled_default=False,
    ),
    ProtectSensorEntityDescription(
        key="motion_last_trip_time",
        translation_key="last_motion_detected",
        device_class=SensorDeviceClass.TIMESTAMP,
        ufp_public_value="motion_detected_at_dt",
        ufp_capability=SensorFeatureCapability.MOTION,
        entity_registry_enabled_default=False,
    ),
    ProtectSensorEntityDescription(
        key="tampering_last_trip_time",
        translation_key="last_tampering_detected",
        ufp_capability=SensorFeatureCapability.TAMPER,
        device_class=SensorDeviceClass.TIMESTAMP,
        ufp_public_value="tampering_detected_at_dt",
        entity_registry_enabled_default=False,
    ),
    ProtectSensorEntityDescription(
        key="signal_quality",
        translation_key="signal_quality",
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        ufp_public_value="wireless_connection_state.signal_state.signal_quality",
    ),
    # Sensors connect over Bluetooth or SuperLink, which the public API does
    # not tell apart, so the name stays generic.
    ProtectSensorEntityDescription(
        key="signal_strength",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        ufp_public_value="wireless_connection_state.signal_state.signal_strength",
    ),
)

NVR_SENSORS: tuple[ProtectSensorEntityDescription, ...] = (
    ProtectSensorEntityDescription(
        key="storage_utilization",
        translation_key="storage_utilization",
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        ufp_value="storage_stats.utilization",
        precision=2,
    ),
    ProtectSensorEntityDescription(
        key="record_rotating",
        translation_key="type_timelapse_video",
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        ufp_value="storage_stats.storage_distribution.timelapse_recordings.percentage",
        precision=2,
    ),
    ProtectSensorEntityDescription(
        key="record_timelapse",
        translation_key="type_continuous_video",
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        ufp_value="storage_stats.storage_distribution.continuous_recordings.percentage",
        precision=2,
    ),
    ProtectSensorEntityDescription(
        key="record_detections",
        translation_key="type_detections_video",
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        ufp_value="storage_stats.storage_distribution.detections_recordings.percentage",
        precision=2,
    ),
    ProtectSensorEntityDescription(
        key="resolution_HD",
        translation_key="resolution_hd_video",
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        ufp_value="storage_stats.storage_distribution.hd_usage.percentage",
        precision=2,
    ),
    ProtectSensorEntityDescription(
        key="resolution_4K",
        translation_key="resolution_4k_video",
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        ufp_value="storage_stats.storage_distribution.uhd_usage.percentage",
        precision=2,
    ),
    ProtectSensorEntityDescription(
        key="resolution_free",
        translation_key="resolution_free_space",
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        ufp_value="storage_stats.storage_distribution.free.percentage",
        precision=2,
    ),
    ProtectSensorEntityDescription[NVR](
        key="record_capacity",
        translation_key="recording_capacity",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        ufp_value_fn=_get_nvr_recording_capacity,
    ),
)

LIGHT_SENSORS: tuple[ProtectSensorEntityDescription, ...] = (
    ProtectSensorEntityDescription(
        key="motion_last_trip_time",
        translation_key="last_motion_detected",
        device_class=SensorDeviceClass.TIMESTAMP,
        ufp_public_value="last_motion_dt",
        entity_registry_enabled_default=False,
    ),
)

CHIME_SENSORS: tuple[ProtectSensorEntityDescription, ...] = (
    ProtectSensorEntityDescription(
        key="last_ring",
        translation_key="last_ring",
        device_class=SensorDeviceClass.TIMESTAMP,
        ufp_value="last_ring",
    ),
    ProtectSensorEntityDescription(
        key="volume",
        translation_key="volume",
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_value="volume",
        ufp_perm=PermRequired.NO_WRITE,
    ),
)

VIEWER_SENSORS: tuple[ProtectSensorEntityDescription, ...] = (
    ProtectSensorEntityDescription(
        key="viewer",
        translation_key="liveview",
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_value="liveview.name",
        ufp_perm=PermRequired.NO_WRITE,
    ),
)

_MODEL_DESCRIPTIONS: dict[ModelType, Sequence[ProtectEntityDescription]] = {
    ModelType.CAMERA: CAMERA_SENSORS,
    ModelType.SENSOR: SENSE_SENSORS,
    ModelType.LIGHT: LIGHT_SENSORS,
    ModelType.CHIME: CHIME_SENSORS,
    ModelType.VIEWPORT: VIEWER_SENSORS,
}


def _fob_battery_level(fob: Fob) -> int | None:
    """Return the key fob battery percentage, if it has been reported."""
    if (battery := fob.wireless_connection_state.battery_status) is not None:
        return battery.percentage
    return None


def _fob_signal_strength(fob: Fob) -> int | None:
    """Return the key fob Bluetooth signal strength, if it has been reported."""
    if (signal := fob.wireless_connection_state.signal_state) is not None:
        return signal.signal_strength
    return None


def _fob_signal_quality(fob: Fob) -> int | None:
    """Return the key fob signal quality, if it has been reported."""
    if (signal := fob.wireless_connection_state.signal_state) is not None:
        return signal.signal_quality
    return None


def _fob_status(fob: Fob) -> str | None:
    """Return the key fob presence state.

    ``FobAwayState`` carries an ``UNKNOWN`` member that the library coerces
    unrecognized wire values into; map it to ``None`` (unknown state) rather
    than a value the enum sensor's ``options`` do not list.
    """
    if (away_state := fob.away_state) is FobAwayState.UNKNOWN:
        return None
    return away_state.value.lower()


@dataclass(frozen=True, kw_only=True)
class ProtectFobSensorEntityDescription(SensorEntityDescription):
    """Describes a UniFi Protect key fob sensor entity."""

    value_fn: Callable[[Fob], int | str | None]


FOB_SENSORS: tuple[ProtectFobSensorEntityDescription, ...] = (
    ProtectFobSensorEntityDescription(
        key="battery_level",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_fob_battery_level,
    ),
    ProtectFobSensorEntityDescription(
        key="signal_strength",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_fob_signal_strength,
    ),
    ProtectFobSensorEntityDescription(
        key="signal_quality",
        translation_key="signal_quality",
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_fob_signal_quality,
    ),
    ProtectFobSensorEntityDescription(
        key="status",
        translation_key="fob_status",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=["online", "recently_seen", "no_recent_heartbeat", "device_lost"],
        value_fn=_fob_status,
    ),
)


class ProtectFobSensor(ProtectDeviceEntity, SensorEntity):
    """A sensor entity for a UniFi Protect key fob (Public API)."""

    entity_description: ProtectFobSensorEntityDescription
    _state_attrs = ("_attr_available", "_attr_native_value")
    _ufp_uses_public = True

    @callback
    @override
    def _async_update_device_from_protect(self, device: ProtectDeviceType) -> None:
        super()._async_update_device_from_protect(device)
        if (fob := self._ufp_public_obj) is not None:
            self._attr_native_value = self.entity_description.value_fn(cast(Fob, fob))


@callback
def _async_public_entities(
    data: ProtectData, device: PublicDeviceModel
) -> list[Entity]:
    """Return the sensors for one public device."""
    if isinstance(device, Fob):
        return [
            ProtectFobSensor(data, device, description) for description in FOB_SENSORS
        ]
    return list(
        async_all_device_entities(
            data,
            ProtectDeviceSensor,
            model_descriptions=_MODEL_DESCRIPTIONS,
            public_device=device,
        )
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: UFPConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensors for UniFi Protect integration."""
    data = entry.runtime_data

    @callback
    def _add_new_public_device(device: PublicDeviceModel) -> None:
        async_add_entities(_async_public_entities(data, device))

    entry.async_on_unload(
        async_dispatcher_connect(hass, data.public_add_signal, _add_new_public_device)
    )

    async_remove_unsupported_sense_entities(hass, Platform.SENSOR, data, SENSE_SENSORS)

    entities: list[Entity] = []
    # The public bootstrap is primed only with an API key and supported NVR
    # firmware; without it there are no fobs to expose.
    api = data.api
    if api.has_public_bootstrap:
        for fob in api.public_bootstrap.fobs.values():
            entities.extend(_async_public_entities(data, fob))

    if api.is_public_only:
        # The remaining sensors read the private bootstrap; the migrated ones
        # are built from the public devices instead.
        entities.extend(
            async_all_device_entities(
                data, ProtectDeviceSensor, model_descriptions=_MODEL_DESCRIPTIONS
            )
        )
        async_add_entities(entities)
        return

    @callback
    def _add_new_device(device: ProtectAdoptableDeviceModel) -> None:
        async_add_entities(
            async_all_device_entities(
                data,
                ProtectDeviceSensor,
                all_descs=ALL_DEVICES_SENSORS,
                model_descriptions=_MODEL_DESCRIPTIONS,
                ufp_device=device,
            )
        )

    data.async_subscribe_adopt(_add_new_device)
    entities.extend(
        async_all_device_entities(
            data,
            ProtectDeviceSensor,
            all_descs=ALL_DEVICES_SENSORS,
            model_descriptions=_MODEL_DESCRIPTIONS,
        )
    )
    entities.extend(_async_nvr_entities(data))

    async_add_entities(entities)


@callback
def _async_nvr_entities(
    data: ProtectData,
) -> list[BaseProtectEntity]:
    entities: list[BaseProtectEntity] = []
    device = data.api.bootstrap.nvr
    for description in NVR_SENSORS:
        entities.append(ProtectNVRSensor(data, device, description))
        _LOGGER.debug("Adding NVR sensor entity %s", description.name)

    return entities


class BaseProtectSensor(BaseProtectEntity, SensorEntity):
    """A UniFi Protect Sensor Entity."""

    entity_description: ProtectSensorEntityDescription
    _state_attrs = ("_attr_available", "_attr_native_value")

    @callback
    @override
    def _async_update_device_from_protect(self, device: ProtectDeviceType) -> None:
        super()._async_update_device_from_protect(device)
        self._attr_native_value = self.entity_description.get_value(
            self.device, self._ufp_public_obj
        )


class ProtectDeviceSensor(BaseProtectSensor, ProtectDeviceEntity):
    """A Ubiquiti UniFi Protect Sensor."""


class ProtectNVRSensor(BaseProtectSensor, ProtectNVREntity):
    """A Ubiquiti UniFi Protect Sensor."""
