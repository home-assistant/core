"""Component providing select entities for UniFi Protect."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
import logging
from typing import Any, Final

from pyunifiprotect.api import ProtectApiClient
from pyunifiprotect.data import (
    Camera,
    ChimeType,
    DoorbellMessageType,
    Doorlock,
    IRLEDMode,
    Light,
    LightModeEnableType,
    LightModeType,
    MountType,
    ProtectAdoptableDeviceModel,
    ProtectModelWithId,
    RecordingMode,
    Sensor,
    Viewer,
)

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DISPATCH_ADOPT, DOMAIN, TYPE_EMPTY_VALUE
from .data import ProtectData
from .entity import ProtectDeviceEntity, async_all_device_entities
from .models import PermRequired, ProtectSetableKeysMixin, T
from .utils import async_dispatch_id as _ufpd, async_get_light_motion_current

_LOGGER = logging.getLogger(__name__)
_KEY_LIGHT_MOTION = "light_motion"

INFRARED_MODES = [
    {"id": IRLEDMode.AUTO.value, "name": "Auto"},
    {"id": IRLEDMode.ON.value, "name": "Always Enable"},
    {"id": IRLEDMode.AUTO_NO_LED.value, "name": "Auto (Filter Only, no LED's)"},
    {"id": IRLEDMode.OFF.value, "name": "Always Disable"},
]

CHIME_TYPES = [
    {"id": ChimeType.NONE.value, "name": "None"},
    {"id": ChimeType.MECHANICAL.value, "name": "Mechanical"},
    {"id": ChimeType.DIGITAL.value, "name": "Digital"},
]

MOUNT_TYPES = [
    {"id": MountType.NONE.value, "name": "None"},
    {"id": MountType.DOOR.value, "name": "Door"},
    {"id": MountType.WINDOW.value, "name": "Window"},
    {"id": MountType.GARAGE.value, "name": "Garage"},
    {"id": MountType.LEAK.value, "name": "Leak"},
]

LIGHT_MODE_MOTION = "On Motion - Always"
LIGHT_MODE_MOTION_DARK = "On Motion - When Dark"
LIGHT_MODE_DARK = "When Dark"
LIGHT_MODE_OFF = "Manual"
LIGHT_MODES = [LIGHT_MODE_MOTION, LIGHT_MODE_DARK, LIGHT_MODE_OFF]

LIGHT_MODE_TO_SETTINGS = {
    LIGHT_MODE_MOTION: (LightModeType.MOTION.value, LightModeEnableType.ALWAYS.value),
    LIGHT_MODE_MOTION_DARK: (
        LightModeType.MOTION.value,
        LightModeEnableType.DARK.value,
    ),
    LIGHT_MODE_DARK: (LightModeType.WHEN_DARK.value, LightModeEnableType.DARK.value),
    LIGHT_MODE_OFF: (LightModeType.MANUAL.value, None),
}

MOTION_MODE_TO_LIGHT_MODE = [
    {"id": LightModeType.MOTION.value, "name": LIGHT_MODE_MOTION},
    {"id": f"{LightModeType.MOTION.value}Dark", "name": LIGHT_MODE_MOTION_DARK},
    {"id": LightModeType.WHEN_DARK.value, "name": LIGHT_MODE_DARK},
    {"id": LightModeType.MANUAL.value, "name": LIGHT_MODE_OFF},
]

DEVICE_RECORDING_MODES = [
    {"id": mode.value, "name": mode.value.title()} for mode in list(RecordingMode)
]

DEVICE_CLASS_LCD_MESSAGE: Final = "unifiprotect__lcd_message"


@dataclass(frozen=True, kw_only=True)
class ProtectSelectEntityDescription(
    ProtectSetableKeysMixin[T], SelectEntityDescription
):
    """Describes UniFi Protect Select entity."""

    ufp_options: list[dict[str, Any]] | None = None
    ufp_options_fn: Callable[[ProtectApiClient], list[dict[str, Any]]] | None = None
    ufp_enum_type: type[Enum] | None = None


def _get_viewer_options(api: ProtectApiClient) -> list[dict[str, Any]]:
    return [
        {"id": item.id, "name": item.name} for item in api.bootstrap.liveviews.values()
    ]


def _get_doorbell_options(api: ProtectApiClient) -> list[dict[str, Any]]:
    default_message = api.bootstrap.nvr.doorbell_settings.default_message_text
    messages = api.bootstrap.nvr.doorbell_settings.all_messages
    built_messages: list[dict[str, str]] = []

    for item in messages:
        msg_type = item.type.value
        if item.type is DoorbellMessageType.CUSTOM_MESSAGE:
            msg_type = f"{DoorbellMessageType.CUSTOM_MESSAGE.value}:{item.text}"

        built_messages.append({"id": msg_type, "name": item.text})

    return [
        {"id": "", "name": f"Default Message ({default_message})"},
        *built_messages,
    ]


def _get_paired_camera_options(api: ProtectApiClient) -> list[dict[str, Any]]:
    options = [{"id": TYPE_EMPTY_VALUE, "name": "Not Paired"}]
    for camera in api.bootstrap.cameras.values():
        options.append({"id": camera.id, "name": camera.display_name or camera.type})

    return options


def _get_viewer_current(obj: Viewer) -> str:
    return obj.liveview_id


def _get_doorbell_current(obj: Camera) -> str | None:
    if obj.lcd_message is None:
        return None
    return obj.lcd_message.text


async def _set_light_mode(obj: Light, mode: str) -> None:
    lightmode, timing = LIGHT_MODE_TO_SETTINGS[mode]
    await obj.set_light_settings(
        LightModeType(lightmode),
        enable_at=None if timing is None else LightModeEnableType(timing),
    )


async def _set_paired_camera(obj: Light | Sensor | Doorlock, camera_id: str) -> None:
    if camera_id == TYPE_EMPTY_VALUE:
        camera: Camera | None = None
    else:
        camera = obj.api.bootstrap.cameras.get(camera_id)
    await obj.set_paired_camera(camera)


async def _set_doorbell_message(obj: Camera, message: str) -> None:
    if message.startswith(DoorbellMessageType.CUSTOM_MESSAGE.value):
        message = message.split(":")[-1]
        await obj.set_lcd_text(DoorbellMessageType.CUSTOM_MESSAGE, text=message)
    elif message == TYPE_EMPTY_VALUE:
        await obj.set_lcd_text(None)
    else:
        await obj.set_lcd_text(DoorbellMessageType(message))


async def _set_liveview(obj: Viewer, liveview_id: str) -> None:
    liveview = obj.api.bootstrap.liveviews[liveview_id]
    await obj.set_liveview(liveview)


CAMERA_SELECTS: tuple[ProtectSelectEntityDescription, ...] = (
    ProtectSelectEntityDescription(
        key="recording_mode",
        name="Recording Mode",
        icon="mdi:video-outline",
        entity_category=EntityCategory.CONFIG,
        ufp_options=DEVICE_RECORDING_MODES,
        ufp_enum_type=RecordingMode,
        ufp_value="recording_settings.mode",
        ufp_set_method="set_recording_mode",
        ufp_perm=PermRequired.WRITE,
    ),
    ProtectSelectEntityDescription(
        key="infrared",
        name="Infrared Mode",
        icon="mdi:circle-opacity",
        entity_category=EntityCategory.CONFIG,
        ufp_required_field="feature_flags.has_led_ir",
        ufp_options=INFRARED_MODES,
        ufp_enum_type=IRLEDMode,
        ufp_value="isp_settings.ir_led_mode",
        ufp_set_method="set_ir_led_model",
        ufp_perm=PermRequired.WRITE,
    ),
    ProtectSelectEntityDescription[Camera](
        key="doorbell_text",
        name="Doorbell Text",
        icon="mdi:card-text",
        entity_category=EntityCategory.CONFIG,
        device_class=DEVICE_CLASS_LCD_MESSAGE,
        ufp_required_field="feature_flags.has_lcd_screen",
        ufp_value_fn=_get_doorbell_current,
        ufp_options_fn=_get_doorbell_options,
        ufp_set_method_fn=_set_doorbell_message,
        ufp_perm=PermRequired.WRITE,
    ),
    ProtectSelectEntityDescription(
        key="chime_type",
        name="Chime Type",
        icon="mdi:bell",
        entity_category=EntityCategory.CONFIG,
        ufp_required_field="feature_flags.has_chime",
        ufp_options=CHIME_TYPES,
        ufp_enum_type=ChimeType,
        ufp_value="chime_type",
        ufp_set_method="set_chime_type",
        ufp_perm=PermRequired.WRITE,
    ),
)

LIGHT_SELECTS: tuple[ProtectSelectEntityDescription, ...] = (
    ProtectSelectEntityDescription[Light](
        key=_KEY_LIGHT_MOTION,
        name="Light Mode",
        icon="mdi:spotlight",
        entity_category=EntityCategory.CONFIG,
        ufp_options=MOTION_MODE_TO_LIGHT_MODE,
        ufp_value_fn=async_get_light_motion_current,
        ufp_set_method_fn=_set_light_mode,
        ufp_perm=PermRequired.WRITE,
    ),
    ProtectSelectEntityDescription[Light](
        key="paired_camera",
        name="Paired Camera",
        icon="mdi:cctv",
        entity_category=EntityCategory.CONFIG,
        ufp_value="camera_id",
        ufp_options_fn=_get_paired_camera_options,
        ufp_set_method_fn=_set_paired_camera,
        ufp_perm=PermRequired.WRITE,
    ),
)

SENSE_SELECTS: tuple[ProtectSelectEntityDescription, ...] = (
    ProtectSelectEntityDescription(
        key="mount_type",
        name="Mount Type",
        icon="mdi:screwdriver",
        entity_category=EntityCategory.CONFIG,
        ufp_options=MOUNT_TYPES,
        ufp_enum_type=MountType,
        ufp_value="mount_type",
        ufp_set_method="set_mount_type",
        ufp_perm=PermRequired.WRITE,
    ),
    ProtectSelectEntityDescription[Sensor](
        key="paired_camera",
        name="Paired Camera",
        icon="mdi:cctv",
        entity_category=EntityCategory.CONFIG,
        ufp_value="camera_id",
        ufp_options_fn=_get_paired_camera_options,
        ufp_set_method_fn=_set_paired_camera,
        ufp_perm=PermRequired.WRITE,
    ),
)

DOORLOCK_SELECTS: tuple[ProtectSelectEntityDescription, ...] = (
    ProtectSelectEntityDescription[Doorlock](
        key="paired_camera",
        name="Paired Camera",
        icon="mdi:cctv",
        entity_category=EntityCategory.CONFIG,
        ufp_value="camera_id",
        ufp_options_fn=_get_paired_camera_options,
        ufp_set_method_fn=_set_paired_camera,
        ufp_perm=PermRequired.WRITE,
    ),
)

VIEWER_SELECTS: tuple[ProtectSelectEntityDescription, ...] = (
    ProtectSelectEntityDescription[Viewer](
        key="viewer",
        name="Liveview",
        icon="mdi:view-dashboard",
        entity_category=None,
        ufp_options_fn=_get_viewer_options,
        ufp_value_fn=_get_viewer_current,
        ufp_set_method_fn=_set_liveview,
        ufp_perm=PermRequired.WRITE,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up number entities for UniFi Protect integration."""
    data: ProtectData = hass.data[DOMAIN][entry.entry_id]

    async def _add_new_device(device: ProtectAdoptableDeviceModel) -> None:
        entities = async_all_device_entities(
            data,
            ProtectSelects,
            camera_descs=CAMERA_SELECTS,
            light_descs=LIGHT_SELECTS,
            sense_descs=SENSE_SELECTS,
            viewer_descs=VIEWER_SELECTS,
            lock_descs=DOORLOCK_SELECTS,
            ufp_device=device,
        )
        async_add_entities(entities)

    entry.async_on_unload(
        async_dispatcher_connect(hass, _ufpd(entry, DISPATCH_ADOPT), _add_new_device)
    )

    entities: list[ProtectDeviceEntity] = async_all_device_entities(
        data,
        ProtectSelects,
        camera_descs=CAMERA_SELECTS,
        light_descs=LIGHT_SELECTS,
        sense_descs=SENSE_SELECTS,
        viewer_descs=VIEWER_SELECTS,
        lock_descs=DOORLOCK_SELECTS,
    )

    async_add_entities(entities)


class ProtectSelects(ProtectDeviceEntity, SelectEntity):
    """A UniFi Protect Select Entity."""

    device: Camera | Light | Viewer
    entity_description: ProtectSelectEntityDescription

    def __init__(
        self,
        data: ProtectData,
        device: Camera | Light | Viewer,
        description: ProtectSelectEntityDescription,
    ) -> None:
        """Initialize the unifi protect select entity."""
        self._async_set_options(data, description)
        super().__init__(data, device, description)
        self._attr_name = f"{self.device.display_name} {self.entity_description.name}"

    @callback
    def _async_update_device_from_protect(self, device: ProtectModelWithId) -> None:
        super()._async_update_device_from_protect(device)
        entity_description = self.entity_description
        # entities with categories are not exposed for voice
        # and safe to update dynamically
        if (
            entity_description.entity_category is not None
            and entity_description.ufp_options_fn is not None
        ):
            _LOGGER.debug(
                "Updating dynamic select options for %s", entity_description.name
            )
            self._async_set_options(self.data, entity_description)
        if (unifi_value := entity_description.get_ufp_value(device)) is None:
            unifi_value = TYPE_EMPTY_VALUE
        self._attr_current_option = self._unifi_to_hass_options.get(
            unifi_value, unifi_value
        )

    @callback
    def _async_set_options(
        self, data: ProtectData, description: ProtectSelectEntityDescription
    ) -> None:
        """Set options attributes from UniFi Protect device."""
        if (ufp_options := description.ufp_options) is not None:
            options = ufp_options
        else:
            assert description.ufp_options_fn is not None
            options = description.ufp_options_fn(data.api)

        self._attr_options = [item["name"] for item in options]
        self._hass_to_unifi_options = {item["name"]: item["id"] for item in options}
        self._unifi_to_hass_options = {item["id"]: item["name"] for item in options}

    async def async_select_option(self, option: str) -> None:
        """Change the Select Entity Option."""

        # Light Motion is a bit different
        if self.entity_description.key == _KEY_LIGHT_MOTION:
            assert self.entity_description.ufp_set_method_fn is not None
            await self.entity_description.ufp_set_method_fn(self.device, option)
            return

        unifi_value = self._hass_to_unifi_options[option]
        if self.entity_description.ufp_enum_type is not None:
            unifi_value = self.entity_description.ufp_enum_type(unifi_value)
        await self.entity_description.ufp_set(self.device, unifi_value)

    @callback
    def _async_get_state_attrs(self) -> tuple[Any, ...]:
        """Retrieve data that goes into the current state of the entity.

        Called before and after updating entity and state is only written if there
        is a change.
        """

        return (self._attr_available, self._attr_options, self._attr_current_option)
