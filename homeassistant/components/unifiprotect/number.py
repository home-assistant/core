"""Component providing number entities for UniFi Protect."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import timedelta

from uiprotect.data import (
    Camera,
    Doorlock,
    Light,
    ModelType,
    ProtectAdoptableDeviceModel,
)

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .data import ProtectData, ProtectDeviceType, UFPConfigEntry
from .entity import (
    PermRequired,
    ProtectDeviceEntity,
    ProtectEntityDescription,
    ProtectSetableKeysMixin,
    T,
    async_all_device_entities,
)


@dataclass(frozen=True, kw_only=True)
class ProtectNumberEntityDescription(
    ProtectSetableKeysMixin[T], NumberEntityDescription
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
        name="Wide dynamic range",
        icon="mdi:state-machine",
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
        name="Microphone level",
        icon="mdi:microphone",
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
        key="zoom_position",
        name="Zoom level",
        icon="mdi:magnify-plus-outline",
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
        name="Chime duration",
        icon="mdi:bell",
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
        name="Infrared custom lux trigger",
        icon="mdi:white-balance-sunny",
        entity_category=EntityCategory.CONFIG,
        ufp_min=1,
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
        name="Motion sensitivity",
        icon="mdi:walk",
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
        name="Auto-shutoff duration",
        icon="mdi:camera-timer",
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
        name="Motion sensitivity",
        icon="mdi:walk",
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
        name="Auto-lock timeout",
        icon="mdi:walk",
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
        name="Volume",
        icon="mdi:speaker",
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


async def async_setup_entry(
    hass: HomeAssistant,
    entry: UFPConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up number entities for UniFi Protect integration."""
    data = entry.runtime_data

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

    data.async_subscribe_adopt(_add_new_device)
    async_add_entities(
        async_all_device_entities(
            data,
            ProtectNumbers,
            model_descriptions=_MODEL_DESCRIPTIONS,
        )
    )


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

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        await self.entity_description.ufp_set(self.device, value)
