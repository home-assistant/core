"""Component providing number entities for UniFi Protect."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import timedelta
import logging

from uiprotect.data import (
    Camera,
    Chime,
    Doorlock,
    Light,
    ModelType,
    ProtectAdoptableDeviceModel,
)

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .data import ProtectData, ProtectDeviceType, UFPConfigEntry
from .entity import (
    PermRequired,
    ProtectDeviceEntity,
    ProtectEntityDescription,
    ProtectSettableKeysMixin,
    T,
    async_all_device_entities,
)
from .utils import async_ufp_instance_command

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class ProtectNumberEntityDescription(
    ProtectSettableKeysMixin[T], NumberEntityDescription
):
    """Describes UniFi Protect Number entity."""

    ufp_max: int | float
    ufp_min: int | float
    ufp_step: int | float


def _get_pir_duration(obj: Light) -> int:
    return int(obj.light_device_settings.pir_duration.total_seconds())


async def _set_pir_duration(obj: Light, value: float) -> None:
    await obj.set_duration(timedelta(seconds=value))


def _get_auto_close(obj: Doorlock) -> int:
    return int(obj.auto_close_time.total_seconds())


async def _set_auto_close(obj: Doorlock, value: float) -> None:
    await obj.set_auto_close_time(timedelta(seconds=value))


def _get_chime_duration(obj: Camera) -> int:
    return int(obj.chime_duration_seconds)


CAMERA_NUMBERS: tuple[ProtectNumberEntityDescription, ...] = (
    ProtectNumberEntityDescription(
        key="wdr_value",
        translation_key="wide_dynamic_range",
        entity_category=EntityCategory.CONFIG,
        ufp_min=0,
        ufp_max=3,
        ufp_step=1,
        ufp_required_field="feature_flags.has_wdr",
        ufp_value="isp_settings.wdr",
        ufp_set_method="set_wdr_level",
        ufp_perm=PermRequired.WRITE,
    ),
    ProtectNumberEntityDescription(
        key="mic_level",
        translation_key="microphone_level",
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=PERCENTAGE,
        ufp_min=0,
        ufp_max=100,
        ufp_step=1,
        ufp_required_field="has_mic",
        ufp_value="mic_volume",
        ufp_enabled="feature_flags.has_mic",
        ufp_set_method="set_mic_volume",
        ufp_perm=PermRequired.WRITE,
    ),
    ProtectNumberEntityDescription(
        key="system_sounds_volume",
        translation_key="system_sounds_volume",
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=PERCENTAGE,
        ufp_min=0,
        ufp_max=100,
        ufp_step=1,
        ufp_required_field="feature_flags.has_speaker",
        ufp_value="speaker_settings.volume",
        ufp_enabled="feature_flags.has_speaker",
        ufp_set_method="set_volume",
        ufp_perm=PermRequired.WRITE,
    ),
    ProtectNumberEntityDescription(
        key="doorbell_ring_volume",
        translation_key="doorbell_ring_volume",
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=PERCENTAGE,
        ufp_min=0,
        ufp_max=100,
        ufp_step=1,
        ufp_required_field="feature_flags.is_doorbell",
        ufp_value="speaker_settings.ring_volume",
        ufp_enabled="feature_flags.is_doorbell",
        ufp_set_method="set_ring_volume",
        ufp_perm=PermRequired.WRITE,
    ),
    ProtectNumberEntityDescription(
        key="zoom_position",
        translation_key="zoom_level",
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=PERCENTAGE,
        ufp_min=0,
        ufp_max=100,
        ufp_step=1,
        ufp_required_field="feature_flags.can_optical_zoom",
        ufp_value="isp_settings.zoom_position",
        ufp_set_method="set_camera_zoom",
        ufp_perm=PermRequired.WRITE,
    ),
    ProtectNumberEntityDescription(
        key="chime_duration",
        translation_key="chime_duration",
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        ufp_min=1,
        ufp_max=10,
        ufp_step=0.1,
        ufp_required_field="feature_flags.has_chime",
        ufp_enabled="is_digital_chime",
        ufp_value_fn=_get_chime_duration,
        ufp_set_method="set_chime_duration",
        ufp_perm=PermRequired.WRITE,
    ),
    ProtectNumberEntityDescription(
        key="icr_lux",
        translation_key="infrared_custom_lux_trigger",
        entity_category=EntityCategory.CONFIG,
        ufp_min=0,
        ufp_max=30,
        ufp_step=1,
        ufp_required_field="feature_flags.has_led_ir",
        ufp_value="icr_lux_display",
        ufp_set_method="set_icr_custom_lux",
        ufp_enabled="is_ir_led_slider_enabled",
        ufp_perm=PermRequired.WRITE,
    ),
)

LIGHT_NUMBERS: tuple[ProtectNumberEntityDescription, ...] = (
    ProtectNumberEntityDescription(
        key="sensitivity",
        translation_key="motion_sensitivity",
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=PERCENTAGE,
        ufp_min=0,
        ufp_max=100,
        ufp_step=1,
        ufp_required_field=None,
        ufp_value="light_device_settings.pir_sensitivity",
        ufp_set_method="set_sensitivity",
        ufp_perm=PermRequired.WRITE,
    ),
    ProtectNumberEntityDescription[Light](
        key="duration",
        translation_key="auto_shutoff_duration",
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        ufp_min=15,
        ufp_max=900,
        ufp_step=15,
        ufp_required_field=None,
        ufp_value_fn=_get_pir_duration,
        ufp_set_method_fn=_set_pir_duration,
        ufp_perm=PermRequired.WRITE,
    ),
)

SENSE_NUMBERS: tuple[ProtectNumberEntityDescription, ...] = (
    ProtectNumberEntityDescription(
        key="sensitivity",
        translation_key="motion_sensitivity",
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=PERCENTAGE,
        ufp_min=0,
        ufp_max=100,
        ufp_step=1,
        ufp_required_field=None,
        ufp_value="motion_settings.sensitivity",
        ufp_set_method="set_motion_sensitivity",
        ufp_perm=PermRequired.WRITE,
    ),
)

DOORLOCK_NUMBERS: tuple[ProtectNumberEntityDescription, ...] = (
    ProtectNumberEntityDescription[Doorlock](
        key="auto_lock_time",
        translation_key="auto_lock_timeout",
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        ufp_min=0,
        ufp_max=3600,
        ufp_step=15,
        ufp_required_field=None,
        ufp_value_fn=_get_auto_close,
        ufp_set_method_fn=_set_auto_close,
        ufp_perm=PermRequired.WRITE,
    ),
)

CHIME_NUMBERS: tuple[ProtectNumberEntityDescription, ...] = (
    ProtectNumberEntityDescription(
        key="volume",
        translation_key="volume",
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=PERCENTAGE,
        ufp_min=0,
        ufp_max=100,
        ufp_step=1,
        ufp_value="volume",
        ufp_set_method="set_volume",
        ufp_perm=PermRequired.WRITE,
    ),
)
_MODEL_DESCRIPTIONS: dict[ModelType, Sequence[ProtectEntityDescription]] = {
    ModelType.CAMERA: CAMERA_NUMBERS,
    ModelType.LIGHT: LIGHT_NUMBERS,
    ModelType.SENSOR: SENSE_NUMBERS,
    ModelType.DOORLOCK: DOORLOCK_NUMBERS,
    ModelType.CHIME: CHIME_NUMBERS,
}


def _async_chime_ring_volume_entities(
    data: ProtectData,
    chime: Chime,
) -> list[ChimeRingVolumeNumber]:
    """Generate ring volume entities for each paired camera on a chime."""
    entities: list[ChimeRingVolumeNumber] = []

    if not chime.is_adopted_by_us:
        return entities

    auth_user = data.api.bootstrap.auth_user
    if not chime.can_write(auth_user):
        return entities

    for ring_setting in chime.ring_settings:
        camera = data.api.bootstrap.cameras.get(ring_setting.camera_id)
        if camera is None:
            _LOGGER.debug(
                "Camera %s not found for chime %s ring volume",
                ring_setting.camera_id,
                chime.display_name,
            )
            continue
        entities.append(ChimeRingVolumeNumber(data, chime, camera))

    return entities


def _async_all_chime_ring_volume_entities(
    data: ProtectData,
    chime: Chime | None = None,
) -> list[ChimeRingVolumeNumber]:
    """Generate all ring volume entities for chimes."""
    entities: list[ChimeRingVolumeNumber] = []

    if chime is not None:
        return _async_chime_ring_volume_entities(data, chime)

    for device in data.get_by_types({ModelType.CHIME}):
        if isinstance(device, Chime):
            entities.extend(_async_chime_ring_volume_entities(data, device))

    return entities


async def async_setup_entry(
    hass: HomeAssistant,
    entry: UFPConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up number entities for UniFi Protect integration."""
    data = entry.runtime_data

    @callback
    def _add_new_device(device: ProtectAdoptableDeviceModel) -> None:
        entities = async_all_device_entities(
            data,
            ProtectNumbers,
            model_descriptions=_MODEL_DESCRIPTIONS,
            ufp_device=device,
        )
        # Add ring volume entities for chimes
        if isinstance(device, Chime):
            entities += _async_all_chime_ring_volume_entities(data, device)
        async_add_entities(entities)

    data.async_subscribe_adopt(_add_new_device)
    entities = async_all_device_entities(
        data,
        ProtectNumbers,
        model_descriptions=_MODEL_DESCRIPTIONS,
    )
    # Add ring volume entities for all chimes
    entities += _async_all_chime_ring_volume_entities(data)
    async_add_entities(entities)


class ProtectNumbers(ProtectDeviceEntity, NumberEntity):
    """A UniFi Protect Number Entity."""

    device: Camera | Light
    entity_description: ProtectNumberEntityDescription
    _state_attrs = ("_attr_available", "_attr_native_value")

    def __init__(
        self,
        data: ProtectData,
        device: Camera | Light,
        description: ProtectNumberEntityDescription,
    ) -> None:
        """Initialize the Number Entities."""
        super().__init__(data, device, description)
        self._attr_native_max_value = self.entity_description.ufp_max
        self._attr_native_min_value = self.entity_description.ufp_min
        self._attr_native_step = self.entity_description.ufp_step

    @callback
    def _async_update_device_from_protect(self, device: ProtectDeviceType) -> None:
        super()._async_update_device_from_protect(device)
        self._attr_native_value = self.entity_description.get_ufp_value(self.device)

    @async_ufp_instance_command
    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        await self.entity_description.ufp_set(self.device, value)


class ChimeRingVolumeNumber(ProtectDeviceEntity, NumberEntity):
    """A UniFi Protect Number Entity for ring volume per camera on a chime."""

    device: Chime
    _state_attrs = ("_attr_available", "_attr_native_value")
    _attr_native_max_value: float = 100
    _attr_native_min_value: float = 0
    _attr_native_step: float = 1
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        data: ProtectData,
        chime: Chime,
        camera: Camera,
    ) -> None:
        """Initialize the ring volume number entity."""
        self._camera_id = camera.id
        # Use chime MAC and camera ID for unique ID
        super().__init__(data, chime)
        self._attr_unique_id = f"{chime.mac}_ring_volume_{camera.id}"
        self._attr_translation_key = "chime_ring_volume"
        self._attr_translation_placeholders = {"camera_name": camera.display_name}
        # BaseProtectEntity sets _attr_name = None when no description is passed,
        # which prevents translation_key from being used. Delete to enable translations.
        del self._attr_name

    @callback
    def _async_update_device_from_protect(self, device: ProtectDeviceType) -> None:
        """Update entity from protect device."""
        super()._async_update_device_from_protect(device)
        self._attr_native_value = self._get_ring_volume()

    def _get_ring_volume(self) -> int | None:
        """Get the ring volume for this camera from the chime's ring settings."""
        for ring_setting in self.device.ring_settings:
            if ring_setting.camera_id == self._camera_id:
                return ring_setting.volume
        return None

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        # Entity is unavailable if the camera is no longer paired with the chime
        return super().available and self._get_ring_volume() is not None

    @async_ufp_instance_command
    async def async_set_native_value(self, value: float) -> None:
        """Set new ring volume value."""
        camera = self.data.api.bootstrap.cameras.get(self._camera_id)
        if camera is None:
            _LOGGER.warning(
                "Cannot set ring volume: camera %s not found", self._camera_id
            )
            return
        await self.device.set_volume_for_camera_public(camera, int(value))
