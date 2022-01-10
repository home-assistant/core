"""This component provides select entities for UniFi Protect."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from enum import Enum
import logging
from typing import Any, Final

from pyunifiprotect.api import ProtectApiClient
from pyunifiprotect.data import (
    Camera,
    DoorbellMessageType,
    IRLEDMode,
    Light,
    LightModeEnableType,
    LightModeType,
    RecordingMode,
    Viewer,
)
import voluptuous as vol

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity import EntityCategory
from homeassistant.util.dt import utcnow

from .const import ATTR_DURATION, ATTR_MESSAGE, DOMAIN, TYPE_EMPTY_VALUE
from .data import ProtectData
from .entity import ProtectDeviceEntity, async_all_device_entities
from .models import ProtectSetableKeysMixin

_LOGGER = logging.getLogger(__name__)
_KEY_LIGHT_MOTION = "light_motion"

INFRARED_MODES = [
    {"id": IRLEDMode.AUTO.value, "name": "Auto"},
    {"id": IRLEDMode.ON.value, "name": "Always Enable"},
    {"id": IRLEDMode.AUTO_NO_LED.value, "name": "Auto (Filter Only, no LED's)"},
    {"id": IRLEDMode.OFF.value, "name": "Always Disable"},
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

SERVICE_SET_DOORBELL_MESSAGE = "set_doorbell_message"

SET_DOORBELL_LCD_MESSAGE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
        vol.Required(ATTR_MESSAGE): cv.string,
        vol.Optional(ATTR_DURATION, default=""): cv.string,
    }
)


@dataclass
class ProtectSelectEntityDescription(ProtectSetableKeysMixin, SelectEntityDescription):
    """Describes UniFi Protect Select entity."""

    ufp_options: list[dict[str, Any]] | None = None
    ufp_options_callable: Callable[
        [ProtectApiClient], list[dict[str, Any]]
    ] | None = None
    ufp_enum_type: type[Enum] | None = None
    ufp_set_method: str | None = None


def _get_viewer_options(api: ProtectApiClient) -> list[dict[str, Any]]:
    return [
        {"id": item.id, "name": item.name} for item in api.bootstrap.liveviews.values()
    ]


def _get_doorbell_options(api: ProtectApiClient) -> list[dict[str, Any]]:
    default_message = api.bootstrap.nvr.doorbell_settings.default_message_text
    messages = api.bootstrap.nvr.doorbell_settings.all_messages
    built_messages = ({"id": item.type.value, "name": item.text} for item in messages)

    return [
        {"id": "", "name": f"Default Message ({default_message})"},
        *built_messages,
    ]


def _get_paired_camera_options(api: ProtectApiClient) -> list[dict[str, Any]]:
    options = [{"id": TYPE_EMPTY_VALUE, "name": "Not Paired"}]
    for camera in api.bootstrap.cameras.values():
        options.append({"id": camera.id, "name": camera.name})

    return options


def _get_viewer_current(obj: Any) -> str:
    assert isinstance(obj, Viewer)
    return obj.liveview_id


def _get_light_motion_current(obj: Any) -> str:
    assert isinstance(obj, Light)
    # a bit of extra to allow On Motion Always/Dark
    if (
        obj.light_mode_settings.mode == LightModeType.MOTION
        and obj.light_mode_settings.enable_at == LightModeEnableType.DARK
    ):
        return f"{LightModeType.MOTION.value}Dark"
    return obj.light_mode_settings.mode.value


def _get_doorbell_current(obj: Any) -> str | None:
    assert isinstance(obj, Camera)
    if obj.lcd_message is None:
        return None
    return obj.lcd_message.text


async def _set_light_mode(obj: Any, mode: str) -> None:
    assert isinstance(obj, Light)
    lightmode, timing = LIGHT_MODE_TO_SETTINGS[mode]
    await obj.set_light_settings(
        LightModeType(lightmode),
        enable_at=None if timing is None else LightModeEnableType(timing),
    )


async def _set_paired_camera(obj: Any, camera_id: str) -> None:
    assert isinstance(obj, Light)
    if camera_id == TYPE_EMPTY_VALUE:
        camera: Camera | None = None
    else:
        camera = obj.api.bootstrap.cameras.get(camera_id)
    await obj.set_paired_camera(camera)


async def _set_doorbell_message(obj: Any, message: str) -> None:
    assert isinstance(obj, Camera)
    if message.startswith(DoorbellMessageType.CUSTOM_MESSAGE.value):
        await obj.set_lcd_text(DoorbellMessageType.CUSTOM_MESSAGE, text=message)
    elif message == TYPE_EMPTY_VALUE:
        await obj.set_lcd_text(None)
    else:
        await obj.set_lcd_text(DoorbellMessageType(message))


async def _set_liveview(obj: Any, liveview_id: str) -> None:
    assert isinstance(obj, Viewer)
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
    ),
    ProtectSelectEntityDescription(
        key="doorbell_text",
        name="Doorbell Text",
        icon="mdi:card-text",
        entity_category=EntityCategory.CONFIG,
        device_class=DEVICE_CLASS_LCD_MESSAGE,
        ufp_required_field="feature_flags.has_lcd_screen",
        ufp_value_fn=_get_doorbell_current,
        ufp_options_callable=_get_doorbell_options,
        ufp_set_method_fn=_set_doorbell_message,
    ),
)

LIGHT_SELECTS: tuple[ProtectSelectEntityDescription, ...] = (
    ProtectSelectEntityDescription(
        key=_KEY_LIGHT_MOTION,
        name="Light Mode",
        icon="mdi:spotlight",
        entity_category=EntityCategory.CONFIG,
        ufp_options=MOTION_MODE_TO_LIGHT_MODE,
        ufp_value_fn=_get_light_motion_current,
        ufp_set_method_fn=_set_light_mode,
    ),
    ProtectSelectEntityDescription(
        key="paired_camera",
        name="Paired Camera",
        icon="mdi:cctv",
        entity_category=EntityCategory.CONFIG,
        ufp_value="camera_id",
        ufp_options_callable=_get_paired_camera_options,
        ufp_set_method_fn=_set_paired_camera,
    ),
)

VIEWER_SELECTS: tuple[ProtectSelectEntityDescription, ...] = (
    ProtectSelectEntityDescription(
        key="viewer",
        name="Liveview",
        icon="mdi:view-dashboard",
        entity_category=None,
        ufp_options_callable=_get_viewer_options,
        ufp_value_fn=_get_viewer_current,
        ufp_set_method_fn=_set_liveview,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: entity_platform.AddEntitiesCallback,
) -> None:
    """Set up number entities for UniFi Protect integration."""
    data: ProtectData = hass.data[DOMAIN][entry.entry_id]
    entities: list[ProtectDeviceEntity] = async_all_device_entities(
        data,
        ProtectSelects,
        camera_descs=CAMERA_SELECTS,
        light_descs=LIGHT_SELECTS,
        viewer_descs=VIEWER_SELECTS,
    )

    async_add_entities(entities)
    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_SET_DOORBELL_MESSAGE,
        SET_DOORBELL_LCD_MESSAGE_SCHEMA,
        "async_set_doorbell_message",
    )


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
        super().__init__(data, device, description)
        self._attr_name = f"{self.device.name} {self.entity_description.name}"
        self._async_set_options()

    @callback
    def _async_update_device_from_protect(self) -> None:
        super()._async_update_device_from_protect()

        # entities with categories are not exposed for voice and safe to update dynamically
        if (
            self.entity_description.entity_category is not None
            and self.entity_description.ufp_options_callable is not None
        ):
            _LOGGER.debug(
                "Updating dynamic select options for %s", self.entity_description.name
            )
            self._async_set_options()

    @callback
    def _async_set_options(self) -> None:
        """Set options attributes from UniFi Protect device."""

        if self.entity_description.ufp_options is not None:
            options = self.entity_description.ufp_options
        else:
            assert self.entity_description.ufp_options_callable is not None
            options = self.entity_description.ufp_options_callable(self.data.api)

        self._attr_options = [item["name"] for item in options]
        self._hass_to_unifi_options = {item["name"]: item["id"] for item in options}
        self._unifi_to_hass_options = {item["id"]: item["name"] for item in options}

    @property
    def current_option(self) -> str:
        """Return the current selected option."""

        unifi_value = self.entity_description.get_ufp_value(self.device)
        if unifi_value is None:
            unifi_value = TYPE_EMPTY_VALUE
        return self._unifi_to_hass_options.get(unifi_value, unifi_value)

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

    async def async_set_doorbell_message(self, message: str, duration: str) -> None:
        """Set LCD Message on Doorbell display."""

        if self.entity_description.device_class != DEVICE_CLASS_LCD_MESSAGE:
            raise HomeAssistantError("Not a doorbell text select entity")

        assert isinstance(self.device, Camera)
        reset_at = None
        timeout_msg = ""
        if duration.isnumeric():
            reset_at = utcnow() + timedelta(minutes=int(duration))
            timeout_msg = f" with timeout of {duration} minute(s)"

        _LOGGER.debug(
            'Setting message for %s to "%s"%s', self.device.name, message, timeout_msg
        )
        await self.device.set_lcd_text(
            DoorbellMessageType.CUSTOM_MESSAGE, message, reset_at=reset_at
        )
