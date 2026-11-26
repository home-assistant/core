"""Component providing binary sensors for UniFi Protect."""

from collections.abc import Callable, Sequence
import dataclasses
import operator
from typing import cast, override

from uiprotect.data import (
    NVR,
    Fob,
    ModelType,
    MountType,
    ProtectAdoptableDeviceModel,
    PublicRelayInput,
    Relay,
    RelayInputState,
    Sensor,
    SmartDetectObjectType,
)
from uiprotect.data.nvr import UOSDisk
from uiprotect.data.public_devices import (
    PublicDeviceModel,
    PublicSensor,
    SensorFeatureCapability,
)

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    async_get_current_platform,
)

from .data import ProtectData, ProtectDeviceType, UFPConfigEntry
from .entity import (
    BaseProtectEntity,
    PermRequired,
    ProtectDeviceEntity,
    ProtectEntityDescription,
    ProtectIsOnEntity,
    ProtectNVREntity,
    ProtectPublicChannelEntity,
    async_all_device_entities,
    async_remove_unsupported_sense_entities,
)

_KEY_DOOR = "door"
PARALLEL_UPDATES = 0

_RELAY_INPUT_STATE_MAP: dict[RelayInputState, bool] = {
    RelayInputState.ON: True,
    RelayInputState.OFF: False,
}


@dataclasses.dataclass(frozen=True, kw_only=True)
class ProtectBinaryEntityDescription(
    ProtectEntityDescription, BinarySensorEntityDescription
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
        translation_key="is_dark",
        ufp_value="is_dark",
    ),
    ProtectBinaryEntityDescription(
        key="system_sounds",
        translation_key="system_sounds",
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_required_field="has_speaker",
        ufp_value="speaker_settings.are_system_sounds_enabled",
        ufp_enabled="feature_flags.has_speaker",
        ufp_perm=PermRequired.NO_WRITE,
    ),
    ProtectBinaryEntityDescription(
        key="motion_enabled",
        translation_key="detections_motion",
        ufp_value="recording_settings.enable_motion_detection",
        ufp_perm=PermRequired.NO_WRITE,
    ),
    ProtectBinaryEntityDescription(
        key="track_person",
        translation_key="tracking_person",
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_required_field="feature_flags.is_ptz",
        ufp_value="is_person_tracking_enabled",
        ufp_perm=PermRequired.NO_WRITE,
    ),
    # Sustained state via the public devices WS (uiprotect pushes a camera
    # update on each detection transition).
    ProtectBinaryEntityDescription(
        key="motion",
        device_class=BinarySensorDeviceClass.MOTION,
        ufp_public_value="is_motion_detected",
        ufp_event_driven=True,
    ),
    ProtectBinaryEntityDescription(
        key="smart_obj_any",
        translation_key="object_detected",
        ufp_required_field="feature_flags.smart_detect_types",
        ufp_public_value="is_smart_currently_detected",
        ufp_event_driven=True,
        entity_registry_enabled_default=False,
    ),
    ProtectBinaryEntityDescription(
        key="smart_obj_person",
        translation_key="person_detected",
        ufp_capability=SmartDetectObjectType.PERSON,
        ufp_public_value="is_person_currently_detected",
        ufp_event_driven=True,
        ufp_public_enabled_fn=operator.attrgetter("is_person_detection_on"),
    ),
    ProtectBinaryEntityDescription(
        key="smart_obj_vehicle",
        translation_key="vehicle_detected",
        ufp_capability=SmartDetectObjectType.VEHICLE,
        ufp_public_value="is_vehicle_currently_detected",
        ufp_event_driven=True,
        ufp_public_enabled_fn=operator.attrgetter("is_vehicle_detection_on"),
    ),
    ProtectBinaryEntityDescription(
        key="smart_obj_animal",
        translation_key="animal_detected",
        ufp_capability=SmartDetectObjectType.ANIMAL,
        ufp_public_value="is_animal_currently_detected",
        ufp_event_driven=True,
        ufp_public_enabled_fn=operator.attrgetter("is_animal_detection_on"),
    ),
    ProtectBinaryEntityDescription(
        key="smart_audio_any",
        translation_key="audio_object_detected",
        ufp_required_field="feature_flags.smart_detect_audio_types",
        ufp_public_value="is_audio_currently_detected",
        ufp_event_driven=True,
        entity_registry_enabled_default=False,
    ),
    ProtectBinaryEntityDescription(
        key="smart_audio_smoke",
        translation_key="smoke_alarm_detected",
        ufp_capability=SmartDetectObjectType.SMOKE,
        ufp_public_value="is_smoke_currently_detected",
        ufp_event_driven=True,
        ufp_public_enabled_fn=operator.attrgetter("is_smoke_detection_on"),
    ),
    ProtectBinaryEntityDescription(
        key="smart_audio_cmonx",
        translation_key="co_alarm_detected",
        device_class=BinarySensorDeviceClass.CO,
        ufp_capability=SmartDetectObjectType.CMONX,
        ufp_public_value="is_cmonx_currently_detected",
        ufp_event_driven=True,
        ufp_public_enabled_fn=operator.attrgetter("is_co_detection_on"),
    ),
    ProtectBinaryEntityDescription(
        key="smart_audio_siren",
        translation_key="siren_detected",
        ufp_capability=SmartDetectObjectType.SIREN,
        ufp_public_value="is_siren_currently_detected",
        ufp_event_driven=True,
        ufp_public_enabled_fn=operator.attrgetter("is_siren_detection_on"),
    ),
    ProtectBinaryEntityDescription(
        key="smart_audio_baby_cry",
        translation_key="baby_cry_detected",
        ufp_capability=SmartDetectObjectType.BABY_CRY,
        ufp_public_value="is_baby_cry_currently_detected",
        ufp_event_driven=True,
        ufp_public_enabled_fn=operator.attrgetter("is_baby_cry_detection_on"),
    ),
    ProtectBinaryEntityDescription(
        key="smart_audio_speak",
        translation_key="speaking_detected",
        ufp_capability=SmartDetectObjectType.SPEAK,
        ufp_public_value="is_speaking_currently_detected",
        ufp_event_driven=True,
        ufp_public_enabled_fn=operator.attrgetter("is_speaking_detection_on"),
    ),
    ProtectBinaryEntityDescription(
        key="smart_audio_bark",
        translation_key="barking_detected",
        ufp_capability=SmartDetectObjectType.BARK,
        ufp_public_value="is_bark_currently_detected",
        ufp_event_driven=True,
        ufp_public_enabled_fn=operator.attrgetter("is_bark_detection_on"),
    ),
    ProtectBinaryEntityDescription(
        key="smart_audio_car_alarm",
        translation_key="car_alarm_detected",
        ufp_capability=SmartDetectObjectType.BURGLAR,
        ufp_public_value="is_car_alarm_currently_detected",
        ufp_event_driven=True,
        ufp_public_enabled_fn=operator.attrgetter("is_car_alarm_detection_on"),
    ),
    ProtectBinaryEntityDescription(
        key="smart_audio_car_horn",
        translation_key="car_horn_detected",
        ufp_capability=SmartDetectObjectType.CAR_HORN,
        ufp_public_value="is_car_horn_currently_detected",
        ufp_event_driven=True,
        ufp_public_enabled_fn=operator.attrgetter("is_car_horn_detection_on"),
    ),
    ProtectBinaryEntityDescription(
        key="smart_audio_glass_break",
        translation_key="glass_break_detected",
        ufp_capability=SmartDetectObjectType.GLASS_BREAK,
        ufp_public_value="is_glass_break_currently_detected",
        ufp_event_driven=True,
        ufp_public_enabled_fn=operator.attrgetter("is_glass_break_detection_on"),
    ),
)

LIGHT_SENSORS: tuple[ProtectBinaryEntityDescription, ...] = (
    ProtectBinaryEntityDescription(
        key="dark",
        translation_key="is_dark",
        ufp_public_value="is_dark",
    ),
    ProtectBinaryEntityDescription(
        key="motion",
        device_class=BinarySensorDeviceClass.MOTION,
        ufp_public_value="is_pir_motion_detected",
    ),
)

# The mountable sensors can be remounted at run-time which
# means they can change their device class at run-time.
MOUNTABLE_SENSE_SENSORS: tuple[ProtectBinaryEntityDescription, ...] = (
    ProtectBinaryEntityDescription(
        key=_KEY_DOOR,
        translation_key="contact",
        device_class=BinarySensorDeviceClass.DOOR,
        ufp_public_value="is_opened",
        ufp_public_enabled_fn=operator.attrgetter("is_contact_sensor_enabled"),
        ufp_capability=SensorFeatureCapability.OPEN,
    ),
)

SENSE_SENSORS: tuple[ProtectBinaryEntityDescription, ...] = (
    ProtectBinaryEntityDescription(
        key="leak",
        device_class=BinarySensorDeviceClass.MOISTURE,
        ufp_public_value="is_leak_detected",
        ufp_public_enabled_fn=operator.attrgetter("is_leak_detection_enabled"),
        ufp_capability=SensorFeatureCapability.WATER_LEAK,
    ),
    ProtectBinaryEntityDescription(
        key="battery_low",
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_public_value="wireless_connection_state.battery_status.is_low",
    ),
    ProtectBinaryEntityDescription(
        key="motion",
        device_class=BinarySensorDeviceClass.MOTION,
        ufp_public_value="is_motion_detected",
        ufp_public_enabled_fn=operator.attrgetter("is_motion_sensor_enabled"),
        ufp_capability=SensorFeatureCapability.MOTION,
    ),
    ProtectBinaryEntityDescription(
        key="tampering",
        device_class=BinarySensorDeviceClass.TAMPER,
        ufp_public_value="is_tampering_detected",
        ufp_capability=SensorFeatureCapability.TAMPER,
    ),
    ProtectBinaryEntityDescription(
        key="status_light",
        translation_key="status_light",
        entity_category=EntityCategory.DIAGNOSTIC,
        ufp_value="led_settings.is_enabled",
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

    device: Sensor | PublicSensor
    _state_attrs = ("_attr_available", "_attr_is_on", "_attr_device_class")

    @callback
    @override
    def _async_update_device_from_protect(self, device: ProtectDeviceType) -> None:
        super()._async_update_device_from_protect(device)
        # UP Sense can be any of the 3 contact sensor device classes
        mount_type = (
            cast(PublicSensor, public).mount_type
            if (public := self._ufp_public_obj) is not None
            else self.device.mount_type
        )
        self._attr_device_class = MOUNT_DEVICE_CLASS_MAP.get(
            mount_type, BinarySensorDeviceClass.DOOR
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
    @override
    def _async_update_device_from_protect(self, device: ProtectDeviceType) -> None:
        super()._async_update_device_from_protect(device)
        slot = self._disk.slot
        self._attr_available = False
        available = self.data.last_update_success

        # should not be possible since it would require user to
        # _downgrade_ to make ustorage disappear
        assert self.device.system_info.ustorage is not None
        for disk in self.device.system_info.ustorage.disks:
            if disk.slot == slot:
                self._disk = disk
                self._attr_available = available
                break

        self._attr_is_on = not self._disk.is_healthy


class ProtectRelayInputBinarySensor(
    ProtectPublicChannelEntity[PublicRelayInput], BinarySensorEntity
):
    """Binary sensor for a single relay input channel (Public API)."""

    _state_attrs = ("_attr_available", "_attr_is_on")

    def __init__(
        self,
        data: ProtectData,
        relay: Relay,
        relay_input: PublicRelayInput,
    ) -> None:
        """Initialize the relay input binary sensor."""
        # The description key keeps the legacy ``{mac}_relay_input_{id}`` unique ID.
        description = BinarySensorEntityDescription(
            key=f"relay_input_{relay_input.id}", translation_key="relay_input"
        )
        super().__init__(data, relay, description, relay_input.id)
        self._attr_translation_placeholders = {
            "input_name": relay_input.name or str(relay_input.id),
        }

    @callback
    @override
    def _async_get_channel(self, device: PublicDeviceModel) -> PublicRelayInput | None:
        return cast(Relay, device).get_input(self._channel_id)

    @callback
    @override
    def _async_update_from_channel(self, channel: PublicRelayInput) -> None:
        self._attr_is_on = (
            _RELAY_INPUT_STATE_MAP.get(channel.state)
            if channel.state is not None
            else None
        )


MODEL_DESCRIPTIONS_WITH_CLASS = (
    (_MODEL_DESCRIPTIONS, ProtectDeviceBinarySensor),
    (_MOUNTABLE_MODEL_DESCRIPTIONS, MountableProtectDeviceBinarySensor),
)


@callback
def _async_model_entities(
    data: ProtectData,
    *,
    ufp_device: ProtectAdoptableDeviceModel | None = None,
    public_device: PublicDeviceModel | None = None,
) -> list[BaseProtectEntity]:
    entities: list[BaseProtectEntity] = []
    for model_descriptions, klass in MODEL_DESCRIPTIONS_WITH_CLASS:
        entities += async_all_device_entities(
            data,
            klass,
            model_descriptions=model_descriptions,
            ufp_device=ufp_device,
            public_device=public_device,
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


def _fob_battery_low(fob: Fob) -> bool | None:
    """Return whether the key fob battery is low, if it has been reported."""
    if (battery := fob.wireless_connection_state.battery_status) is not None:
        return battery.is_low
    return None


@dataclasses.dataclass(frozen=True, kw_only=True)
class ProtectFobBinaryEntityDescription(BinarySensorEntityDescription):
    """Describes a UniFi Protect key fob binary sensor entity."""

    value_fn: Callable[[Fob], bool | None]


FOB_BINARY_SENSORS: tuple[ProtectFobBinaryEntityDescription, ...] = (
    ProtectFobBinaryEntityDescription(
        key="battery_low",
        device_class=BinarySensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_fob_battery_low,
    ),
)


class ProtectFobBinarySensor(ProtectDeviceEntity, BinarySensorEntity):
    """A binary sensor entity for a UniFi Protect key fob (Public API)."""

    entity_description: ProtectFobBinaryEntityDescription
    _state_attrs = ("_attr_available", "_attr_is_on")
    _ufp_uses_public = True

    @callback
    @override
    def _async_update_device_from_protect(self, device: ProtectDeviceType) -> None:
        super()._async_update_device_from_protect(device)
        if (fob := self._ufp_public_obj) is not None:
            self._attr_is_on = self.entity_description.value_fn(cast(Fob, fob))


async def async_setup_entry(
    hass: HomeAssistant,
    entry: UFPConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up binary sensors for UniFi Protect integration."""
    data = entry.runtime_data
    platform = async_get_current_platform()

    @callback
    def _add_new_public_device(device: PublicDeviceModel) -> None:
        if isinstance(device, Fob):
            async_add_entities(
                ProtectFobBinarySensor(data, device, description)
                for description in FOB_BINARY_SENSORS
            )
            return
        async_add_entities(_async_model_entities(data, public_device=device))

    @callback
    def _add_new_device(device: ProtectAdoptableDeviceModel) -> None:
        async_add_entities(_async_model_entities(data, ufp_device=device))

    entry.async_on_unload(
        async_dispatcher_connect(hass, data.public_add_signal, _add_new_public_device)
    )
    data.async_subscribe_adopt(_add_new_device)
    async_remove_unsupported_sense_entities(
        hass, Platform.BINARY_SENSOR, data, (*SENSE_SENSORS, *MOUNTABLE_SENSE_SENSORS)
    )

    # The public bootstrap is primed only with an API key and supported NVR
    # firmware; without it there are no fobs to expose.
    api = data.api
    if api.has_public_bootstrap:
        async_add_entities(
            ProtectFobBinarySensor(data, fob, description)
            for fob in api.public_bootstrap.fobs.values()
            for description in FOB_BINARY_SENSORS
        )

    @callback
    def _add_relay_inputs(relay: Relay) -> None:
        live_unique_ids = {entity.unique_id for entity in platform.entities.values()}
        async_add_entities(
            [
                ProtectRelayInputBinarySensor(data, relay, relay_input)
                for relay_input in relay.inputs
                if f"{relay.mac}_relay_input_{relay_input.id}" not in live_unique_ids
            ]
        )

    entry.async_on_unload(
        async_dispatcher_connect(hass, data.relay_signal, _add_relay_inputs)
    )
    if api.has_public_bootstrap:
        for relay in api.public_bootstrap.relays.values():
            _add_relay_inputs(relay)

    entities = _async_model_entities(data)
    if not api.is_public_only:
        # NVR disks read the private bootstrap.
        entities += _async_nvr_entities(data)
    async_add_entities(entities)
