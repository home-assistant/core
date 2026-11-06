"""Component providing number entities for UniFi Protect."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import timedelta
import logging
import operator
from typing import cast, override

from uiprotect import ChimeRingtoneNotSetError
from uiprotect.data import Camera, Chime, Light, ModelType, ProtectAdoptableDeviceModel
from uiprotect.data.public_devices import (
    PublicCamera,
    PublicChime,
    PublicDeviceModel,
    PublicLight,
    PublicRingSettings,
    SensorFeatureCapability,
)

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.const import PERCENTAGE, EntityCategory, Platform, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    async_get_current_platform,
)

from .const import DOMAIN
from .data import ProtectData, ProtectDeviceType, UFPConfigEntry
from .entity import (
    PermRequired,
    ProtectDeviceEntity,
    ProtectEntityDescription,
    ProtectPublicChannelEntity,
    ProtectSettableKeysMixin,
    T,
    async_all_device_entities,
    async_remove_unsupported_sense_entities,
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


async def _set_pir_duration(obj: PublicLight, value: float) -> None:
    await obj.set_duration(timedelta(seconds=value))


def _get_chime_duration(obj: Camera) -> int:
    return int(obj.chime_duration_seconds)


async def _set_chime_volume(obj: Chime, value: float) -> None:
    """Set the ring volume of every paired camera on the public chime."""
    if (public := obj.api.public_bootstrap.chimes.get(obj.id)) is None:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="device_not_available",
            translation_placeholders={"device_name": obj.display_name},
        )
    await public.set_volume_for_all_cameras(int(value))


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
        ufp_min=1,
        ufp_max=100,
        ufp_step=1,
        # The public setter refuses a camera whose only microphone is a
        # hot-plugged module, so the gate is the built-in flag in both modes.
        ufp_required_field="feature_flags.has_mic",
        # Protect refuses the setter while the microphone is disabled.
        ufp_public_enabled_fn=operator.attrgetter("is_mic_enabled"),
        ufp_public_value="mic_volume",
        ufp_set_method="set_mic_volume",
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
        ufp_public_value="light_device_settings.pir_sensitivity",
        ufp_set_method="set_sensitivity",
    ),
    ProtectNumberEntityDescription[Light](
        key="duration",
        translation_key="auto_shutoff_duration",
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        ufp_min=15,
        ufp_max=900,
        ufp_step=15,
        ufp_public_value="light_device_settings.pir_duration_seconds",
        ufp_set_method_fn=_set_pir_duration,
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
        ufp_public_value="motion_settings.sensitivity",
        ufp_set_method="set_motion_sensitivity",
        ufp_capability=SensorFeatureCapability.MOTION,
    ),
)

CHIME_NUMBERS: tuple[ProtectNumberEntityDescription, ...] = (
    ProtectNumberEntityDescription[Chime](
        key="volume",
        translation_key="volume",
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=PERCENTAGE,
        ufp_min=0,
        ufp_max=100,
        ufp_step=1,
        ufp_value="volume",
        ufp_set_method_fn=_set_chime_volume,
        ufp_perm=PermRequired.WRITE,
    ),
)
_MODEL_DESCRIPTIONS: dict[ModelType, Sequence[ProtectEntityDescription]] = {
    ModelType.CAMERA: CAMERA_NUMBERS,
    ModelType.LIGHT: LIGHT_NUMBERS,
    ModelType.SENSOR: SENSE_NUMBERS,
    ModelType.CHIME: CHIME_NUMBERS,
}


def _ring_volume_key(camera_id: str) -> str:
    """Return the description key, which keeps the legacy ring volume unique ID."""
    return f"ring_volume_{camera_id}"


@callback
def _async_ring_volume_device(
    data: ProtectData, public: PublicChime
) -> Chime | PublicChime | None:
    """Return the device a chime's ring volumes belong to.

    Hybrid keeps the private chime as the device; public-only uses the public one.
    """
    if data.api.is_public_only:
        return public
    private = data.api.bootstrap.chimes.get(public.id)
    if private is None or not private.is_adopted_by_us:
        return None
    return private


async def async_setup_entry(
    hass: HomeAssistant,
    entry: UFPConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up number entities for UniFi Protect integration."""
    data = entry.runtime_data
    platform = async_get_current_platform()
    async_remove_unsupported_sense_entities(hass, Platform.NUMBER, data, SENSE_NUMBERS)

    @callback
    def _add_ring_volumes(
        public: PublicChime, device: Chime | PublicChime | None = None
    ) -> None:
        if (
            device is None
            and (device := _async_ring_volume_device(data, public)) is None
        ):
            return
        live_unique_ids = {entity.unique_id for entity in platform.entities.values()}
        cameras = data.api.public_bootstrap.cameras
        entities: list[ChimeRingVolumeNumber] = []
        for ring_setting in public.ring_settings:
            camera_id = ring_setting.camera_id
            if (
                camera_id is None
                or f"{device.mac}_{_ring_volume_key(camera_id)}" in live_unique_ids
            ):
                continue
            if (camera := cameras.get(camera_id)) is None:
                # Offered again when the camera is added.
                _LOGGER.debug(
                    "Camera %s not found for chime %s ring volume",
                    camera_id,
                    public.display_name,
                )
                continue
            entities.append(ChimeRingVolumeNumber(data, device, camera))
        async_add_entities(entities)

    @callback
    def _add_new_device(device: ProtectAdoptableDeviceModel) -> None:
        async_add_entities(
            async_all_device_entities(
                data,
                ProtectNumbers,
                model_descriptions=_MODEL_DESCRIPTIONS,
                ufp_device=device,
            )
        )
        if isinstance(device, Chime) and isinstance(
            public := data.async_get_public_device(device), PublicChime
        ):
            _add_ring_volumes(public, device)

    @callback
    def _add_new_public_device(device: PublicDeviceModel) -> None:
        async_add_entities(
            async_all_device_entities(
                data,
                ProtectNumbers,
                model_descriptions=_MODEL_DESCRIPTIONS,
                public_device=device,
            )
        )

    data.async_subscribe_adopt(_add_new_device)
    entry.async_on_unload(
        async_dispatcher_connect(hass, data.public_add_signal, _add_new_public_device)
    )
    entry.async_on_unload(
        async_dispatcher_connect(hass, data.chime_signal, _add_ring_volumes)
    )
    async_add_entities(
        async_all_device_entities(
            data,
            ProtectNumbers,
            model_descriptions=_MODEL_DESCRIPTIONS,
        )
    )
    if data.api.has_public_bootstrap:
        for public in data.api.public_bootstrap.chimes.values():
            _add_ring_volumes(public)


class ProtectNumbers(ProtectDeviceEntity, NumberEntity):
    """A UniFi Protect Number Entity."""

    entity_description: ProtectNumberEntityDescription
    _state_attrs = ("_attr_available", "_attr_native_value")

    def __init__(
        self,
        data: ProtectData,
        device: ProtectDeviceType,
        description: ProtectNumberEntityDescription,
    ) -> None:
        """Initialize the Number Entities."""
        super().__init__(data, device, description)
        self._attr_native_max_value = self.entity_description.ufp_max
        self._attr_native_min_value = self.entity_description.ufp_min
        self._attr_native_step = self.entity_description.ufp_step

    @callback
    @override
    def _async_update_device_from_protect(self, device: ProtectDeviceType) -> None:
        super()._async_update_device_from_protect(device)
        self._attr_native_value = self.entity_description.get_value(
            self.device, self._ufp_public_obj
        )

    @async_ufp_instance_command
    @override
    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        await self.entity_description.ufp_set(self._ufp_set_target(), value)


class ChimeRingVolumeNumber(
    ProtectPublicChannelEntity[PublicRingSettings, str], NumberEntity
):
    """Ring volume of one doorbell paired with a chime (Public API)."""

    _state_attrs = ("_attr_available", "_attr_native_value")

    def __init__(
        self,
        data: ProtectData,
        chime: Chime | PublicChime,
        camera: PublicCamera,
    ) -> None:
        """Initialize the ring volume number entity."""
        description = NumberEntityDescription(
            key=_ring_volume_key(camera.id),
            translation_key="chime_ring_volume",
            entity_category=EntityCategory.CONFIG,
            native_min_value=0,
            native_max_value=100,
            native_step=1,
            native_unit_of_measurement=PERCENTAGE,
        )
        super().__init__(data, chime, description, camera.id)
        self._attr_translation_placeholders = {"camera_name": camera.display_name}

    @callback
    @override
    def _async_get_channel(
        self, device: PublicDeviceModel
    ) -> PublicRingSettings | None:
        ring_setting = cast(PublicChime, device).get_ring_setting(self._channel_id)
        if ring_setting is None or ring_setting.volume is None:
            return None
        return ring_setting

    @callback
    @override
    def _async_update_from_channel(self, channel: PublicRingSettings) -> None:
        self._attr_native_value = channel.volume

    @async_ufp_instance_command
    @override
    async def async_set_native_value(self, value: float) -> None:
        """Set new ring volume value."""
        public = cast(PublicChime, self._ufp_set_target())
        try:
            await public.set_volume_for_camera(self._channel_id, int(value))
        except ChimeRingtoneNotSetError as err:
            # The library checks every paired camera, so name the one it reports.
            camera = self.data.api.public_bootstrap.cameras.get(err.camera_id)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="chime_ringtone_not_set",
                translation_placeholders={
                    "camera_name": camera.display_name if camera else err.camera_id
                },
            ) from err
