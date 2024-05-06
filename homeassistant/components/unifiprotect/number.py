"""Component providing number entities for UniFi Protect."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Any

from pyunifiprotect.data import (
    Camera,
    Doorlock,
    Light,
    ProtectAdoptableDeviceModel,
    ProtectModelWithId,
)

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DISPATCH_ADOPT, DOMAIN
from .data import ProtectData
from .entity import ProtectDeviceEntity, async_all_device_entities
from .models import PermRequired, ProtectSetableKeysMixin, T
from .utils import async_dispatch_id as _ufpd

_LOGGER = logging.getLogger(__name__)


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
    return int(obj.chime_duration.total_seconds())


CAMERA_NUMBERS: tuple[ProtectNumberEntityDescription, ...] = (
    ProtectNumberEntityDescription(
        key="wdr_value",
        name="Wide Dynamic Range",
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
        name="Microphone Level",
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
        name="Zoom Level",
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
        name="Chime Duration",
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
)

LIGHT_NUMBERS: tuple[ProtectNumberEntityDescription, ...] = (
    ProtectNumberEntityDescription(
        key="sensitivity",
        name="Motion Sensitivity",
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
        name="Auto-shutoff Duration",
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
        name="Motion Sensitivity",
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
        name="Auto-lock Timeout",
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


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up number entities for UniFi Protect integration."""
    data: ProtectData = hass.data[DOMAIN][entry.entry_id]

    async def _add_new_device(device: ProtectAdoptableDeviceModel) -> None:
        entities = async_all_device_entities(
            data,
            ProtectNumbers,
            camera_descs=CAMERA_NUMBERS,
            light_descs=LIGHT_NUMBERS,
            sense_descs=SENSE_NUMBERS,
            lock_descs=DOORLOCK_NUMBERS,
            chime_descs=CHIME_NUMBERS,
            ufp_device=device,
        )
        async_add_entities(entities)

    entry.async_on_unload(
        async_dispatcher_connect(hass, _ufpd(entry, DISPATCH_ADOPT), _add_new_device)
    )

    entities: list[ProtectDeviceEntity] = async_all_device_entities(
        data,
        ProtectNumbers,
        camera_descs=CAMERA_NUMBERS,
        light_descs=LIGHT_NUMBERS,
        sense_descs=SENSE_NUMBERS,
        lock_descs=DOORLOCK_NUMBERS,
        chime_descs=CHIME_NUMBERS,
    )

    async_add_entities(entities)


class ProtectNumbers(ProtectDeviceEntity, NumberEntity):
    """A UniFi Protect Number Entity."""

    device: Camera | Light
    entity_description: ProtectNumberEntityDescription

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
    def _async_update_device_from_protect(self, device: ProtectModelWithId) -> None:
        super()._async_update_device_from_protect(device)
        self._attr_native_value = self.entity_description.get_ufp_value(self.device)

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        await self.entity_description.ufp_set(self.device, value)

    @callback
    def _async_get_state_attrs(self) -> tuple[Any, ...]:
        """Retrieve data that goes into the current state of the entity.

        Called before and after updating entity and state is only written if there
        is a change.
        """

        return (self._attr_available, self._attr_native_value)
