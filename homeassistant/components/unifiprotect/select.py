"""Component providing select entities for UniFi Protect."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import Enum
import logging
from typing import Any

from uiprotect.api import ProtectApiClient
from uiprotect.data import (
    Camera,
    ChimeType,
    DoorbellMessageType,
    Doorlock,
    IRLEDMode,
    Light,
    LightModeEnableType,
    LightModeType,
    ModelType,
    MountType,
    ProtectAdoptableDeviceModel,
    RecordingMode,
    Sensor,
    Viewer,
)

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import TYPE_EMPTY_VALUE
from .data import ProtectData, ProtectDeviceType, UFPConfigEntry
from .entity import (
    PermRequired,
    ProtectDeviceEntity,
    ProtectEntityDescription,
    ProtectSettableKeysMixin,
    T,
    async_all_device_entities,
)
from .utils import async_get_light_motion_current, async_ufp_instance_command

_LOGGER = logging.getLogger(__name__)
_KEY_LIGHT_MOTION = "light_motion"
PARALLEL_UPDATES = 0

HDR_MODES = [
    {"id": "always", "name": "always"},
    {"id": "off", "name": "off"},
    {"id": "auto", "name": "auto"},
]

INFRARED_MODES = [
    {"id": IRLEDMode.AUTO.value, "name": "auto"},
    {"id": IRLEDMode.ON.value, "name": "on"},
    {"id": IRLEDMode.AUTO_NO_LED.value, "name": "auto_filter_only"},
    {"id": IRLEDMode.CUSTOM.value, "name": "custom"},
    {"id": IRLEDMode.OFF.value, "name": "off"},
]

CHIME_TYPES = [
    {"id": ChimeType.NONE.value, "name": "none"},
    {"id": ChimeType.MECHANICAL.value, "name": "mechanical"},
    {"id": ChimeType.DIGITAL.value, "name": "digital"},
]

MOUNT_TYPES = [
    {"id": MountType.NONE.value, "name": MountType.NONE.value},
    {"id": MountType.DOOR.value, "name": MountType.DOOR.value},
    {"id": MountType.WINDOW.value, "name": MountType.WINDOW.value},
    {"id": MountType.GARAGE.value, "name": MountType.GARAGE.value},
    {"id": MountType.LEAK.value, "name": MountType.LEAK.value},
]

LIGHT_MODE_MOTION = "motion"
LIGHT_MODE_MOTION_DARK = "motion_dark"
LIGHT_MODE_DARK = "when_dark"
LIGHT_MODE_OFF = "manual"
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
    {"id": f"{LightModeType.MOTION.value}_dark", "name": LIGHT_MODE_MOTION_DARK},
    {"id": LightModeType.WHEN_DARK.value, "name": LIGHT_MODE_DARK},
    {"id": LightModeType.MANUAL.value, "name": LIGHT_MODE_OFF},
]

# PTZ constants - IDs must match state keys in strings.json for translation
PTZ_PRESET_HOME_SLOT = -1
PTZ_PRESET_HOME = "home"
PTZ_PATROL_STOP = "stop"
PTZ_PRESET_IDLE = "idle"
_PTZ_PRESET_RESET_DELAY = 0.5  # Seconds to wait before resetting preset to Idle

_KEY_PTZ_PRESET = "ptz_preset"
_KEY_PTZ_PATROL = "ptz_patrol"

DEVICE_RECORDING_MODES = [
    {"id": mode.value, "name": mode.value} for mode in list(RecordingMode)
]


@dataclass(frozen=True, kw_only=True)
class ProtectSelectEntityDescription(
    ProtectSettableKeysMixin[T], SelectEntityDescription
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
    options.extend(
        {"id": camera.id, "name": camera.display_name or camera.type}
        for camera in api.bootstrap.cameras.values()
    )

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


async def _set_ptz_preset(obj: Camera, preset_slot: str) -> None:
    """Set PTZ camera to preset position."""
    slot = int(preset_slot)
    await obj.ptz_goto_preset_public(slot=slot)


async def _set_ptz_patrol(obj: Camera, patrol_slot: str) -> None:
    """Start or stop PTZ patrol."""
    if patrol_slot == PTZ_PATROL_STOP:
        await obj.ptz_patrol_stop_public()
    else:
        slot = int(patrol_slot)
        await obj.ptz_patrol_start_public(slot=slot)


CAMERA_SELECTS: tuple[ProtectSelectEntityDescription, ...] = (
    ProtectSelectEntityDescription(
        key="recording_mode",
        translation_key="recording_mode",
        entity_category=EntityCategory.CONFIG,
        ufp_options=DEVICE_RECORDING_MODES,
        ufp_enum_type=RecordingMode,
        ufp_value="recording_settings.mode",
        ufp_set_method="set_recording_mode",
        ufp_perm=PermRequired.WRITE,
    ),
    ProtectSelectEntityDescription(
        key="infrared",
        translation_key="infrared_mode",
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
        translation_key="doorbell_text",
        entity_category=EntityCategory.CONFIG,
        ufp_required_field="feature_flags.has_lcd_screen",
        ufp_value_fn=_get_doorbell_current,
        ufp_options_fn=_get_doorbell_options,
        ufp_set_method_fn=_set_doorbell_message,
        ufp_perm=PermRequired.WRITE,
    ),
    ProtectSelectEntityDescription(
        key="chime_type",
        translation_key="chime_type",
        entity_category=EntityCategory.CONFIG,
        ufp_required_field="feature_flags.has_chime",
        ufp_options=CHIME_TYPES,
        ufp_enum_type=ChimeType,
        ufp_value="chime_type",
        ufp_set_method="set_chime_type",
        ufp_perm=PermRequired.WRITE,
    ),
    ProtectSelectEntityDescription(
        key="hdr_mode",
        translation_key="hdr_mode",
        entity_category=EntityCategory.CONFIG,
        ufp_required_field="feature_flags.has_hdr",
        ufp_options=HDR_MODES,
        ufp_value="hdr_mode_display",
        ufp_set_method="set_hdr_mode",
        ufp_perm=PermRequired.WRITE,
    ),
)

# PTZ Select entity descriptions - these need special async handling
PTZ_CAMERA_SELECTS: tuple[ProtectSelectEntityDescription, ...] = (
    ProtectSelectEntityDescription[Camera](
        key=_KEY_PTZ_PRESET,
        translation_key="ptz_preset",
        entity_category=EntityCategory.CONFIG,
        ufp_required_field="feature_flags.is_ptz",
        ufp_set_method_fn=_set_ptz_preset,
        ufp_perm=PermRequired.WRITE,
    ),
    ProtectSelectEntityDescription[Camera](
        key=_KEY_PTZ_PATROL,
        translation_key="ptz_patrol",
        entity_category=EntityCategory.CONFIG,
        ufp_required_field="feature_flags.is_ptz",
        ufp_set_method_fn=_set_ptz_patrol,
        ufp_perm=PermRequired.WRITE,
    ),
)

LIGHT_SELECTS: tuple[ProtectSelectEntityDescription, ...] = (
    ProtectSelectEntityDescription[Light](
        key=_KEY_LIGHT_MOTION,
        translation_key="light_mode",
        entity_category=EntityCategory.CONFIG,
        ufp_options=MOTION_MODE_TO_LIGHT_MODE,
        ufp_value_fn=async_get_light_motion_current,
        ufp_set_method_fn=_set_light_mode,
        ufp_perm=PermRequired.WRITE,
    ),
    ProtectSelectEntityDescription[Light](
        key="paired_camera",
        translation_key="paired_camera",
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
        translation_key="mount_type",
        entity_category=EntityCategory.CONFIG,
        ufp_options=MOUNT_TYPES,
        ufp_enum_type=MountType,
        ufp_value="mount_type",
        ufp_set_method="set_mount_type",
        ufp_perm=PermRequired.WRITE,
    ),
    ProtectSelectEntityDescription[Sensor](
        key="paired_camera",
        translation_key="paired_camera",
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
        translation_key="paired_camera",
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
        translation_key="liveview",
        entity_category=None,
        ufp_options_fn=_get_viewer_options,
        ufp_value_fn=_get_viewer_current,
        ufp_set_method_fn=_set_liveview,
        ufp_perm=PermRequired.WRITE,
    ),
)

_MODEL_DESCRIPTIONS: dict[ModelType, Sequence[ProtectEntityDescription]] = {
    ModelType.CAMERA: CAMERA_SELECTS,
    ModelType.LIGHT: LIGHT_SELECTS,
    ModelType.SENSOR: SENSE_SELECTS,
    ModelType.VIEWPORT: VIEWER_SELECTS,
    ModelType.DOORLOCK: DOORLOCK_SELECTS,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: UFPConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up number entities for UniFi Protect integration."""
    data = entry.runtime_data

    @callback
    def _add_new_device(device: ProtectAdoptableDeviceModel) -> None:
        async_add_entities(
            async_all_device_entities(
                data,
                ProtectSelects,
                model_descriptions=_MODEL_DESCRIPTIONS,
                ufp_device=device,
            )
        )
        # Add PTZ select entities for cameras
        if isinstance(device, Camera):
            hass.async_create_task(
                _async_add_ptz_entities(data, device),
                name="unifiprotect_add_ptz_entities",
            )

    async def _async_add_ptz_entities(
        protect_data: ProtectData, camera: Camera | None = None
    ) -> None:
        """Add PTZ select entities asynchronously."""
        entities: list[ProtectPTZSelect] = []
        cameras = (
            [camera] if camera else list(protect_data.api.bootstrap.cameras.values())
        )

        for cam in cameras:
            if not cam.feature_flags.is_ptz:
                continue
            entities.extend(
                ProtectPTZSelect(protect_data, cam, description)
                for description in PTZ_CAMERA_SELECTS
            )

        if entities:
            async_add_entities(entities)

    data.async_subscribe_adopt(_add_new_device)
    async_add_entities(
        async_all_device_entities(
            data, ProtectSelects, model_descriptions=_MODEL_DESCRIPTIONS
        )
    )
    # Add PTZ entities for existing cameras
    await _async_add_ptz_entities(data)


class ProtectSelects(ProtectDeviceEntity, SelectEntity):
    """A UniFi Protect Select Entity."""

    device: Camera | Light | Viewer
    entity_description: ProtectSelectEntityDescription
    _state_attrs = ("_attr_available", "_attr_options", "_attr_current_option")

    def __init__(
        self,
        data: ProtectData,
        device: Camera | Light | Viewer,
        description: ProtectSelectEntityDescription,
    ) -> None:
        """Initialize the unifi protect select entity."""
        self._async_set_options(data, description)
        super().__init__(data, device, description)

    @callback
    def _async_update_device_from_protect(self, device: ProtectDeviceType) -> None:
        super()._async_update_device_from_protect(device)
        entity_description = self.entity_description
        # entities with categories are not exposed for voice
        # and safe to update dynamically
        if (
            entity_description.entity_category is not None
            and entity_description.ufp_options_fn is not None
        ):
            _LOGGER.debug("Updating dynamic select options for %s", self.entity_id)
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

    @async_ufp_instance_command
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


class ProtectPTZSelect(ProtectDeviceEntity, SelectEntity):
    """A UniFi Protect PTZ Select Entity with async options loading."""

    device: Camera
    entity_description: ProtectSelectEntityDescription
    _state_attrs = ("_attr_available", "_attr_options", "_attr_current_option")

    def __init__(
        self,
        data: ProtectData,
        device: Camera,
        description: ProtectSelectEntityDescription,
    ) -> None:
        """Initialize the PTZ select entity."""
        super().__init__(data, device, description)
        self._attr_options: list[str] = []
        self._attr_current_option: str | None = None
        self._hass_to_unifi_options: dict[str, str] = {}
        self._unifi_to_hass_options: dict[str, str] = {}
        self._reset_timer: asyncio.TimerHandle | None = None

    async def async_added_to_hass(self) -> None:
        """Load PTZ options when entity is added to hass."""
        await super().async_added_to_hass()
        await self._async_load_options()

    async def async_will_remove_from_hass(self) -> None:
        """Cancel any pending timers when entity is removed."""
        if self._reset_timer is not None:
            self._reset_timer.cancel()
            self._reset_timer = None
        await super().async_will_remove_from_hass()

    async def _async_load_options(self) -> None:
        """Load PTZ options from the camera."""
        if self.entity_description.key == _KEY_PTZ_PRESET:
            await self._async_load_preset_options()
        elif self.entity_description.key == _KEY_PTZ_PATROL:
            await self._async_load_patrol_options()

    async def _async_load_preset_options(self) -> None:
        """Load PTZ preset options from the camera."""
        presets = await self.device.get_ptz_presets()

        self._hass_to_unifi_options = {
            PTZ_PRESET_IDLE: PTZ_PRESET_IDLE,
            PTZ_PRESET_HOME: str(PTZ_PRESET_HOME_SLOT),
        }
        self._hass_to_unifi_options.update(
            {preset.name: str(preset.slot) for preset in presets}
        )
        self._unifi_to_hass_options = {
            v: k for k, v in self._hass_to_unifi_options.items()
        }
        self._attr_options = list(self._hass_to_unifi_options)
        self._attr_current_option = PTZ_PRESET_IDLE
        self.async_write_ha_state()

    async def _async_load_patrol_options(self) -> None:
        """Load PTZ patrol options from the camera."""
        patrols = await self.device.get_ptz_patrols()

        self._hass_to_unifi_options = {PTZ_PATROL_STOP: PTZ_PATROL_STOP}
        self._hass_to_unifi_options.update(
            {patrol.name: str(patrol.slot) for patrol in patrols}
        )
        self._unifi_to_hass_options = {
            v: k for k, v in self._hass_to_unifi_options.items()
        }
        self._attr_options = list(self._hass_to_unifi_options)
        # Set initial state based on active patrol
        self._update_patrol_state()
        self.async_write_ha_state()

    def _update_patrol_state(self) -> None:
        """Update the patrol state based on active_patrol_slot."""
        if self.device.active_patrol_slot is not None:
            # A patrol is running - show which one
            slot_str = str(self.device.active_patrol_slot)
            self._attr_current_option = self._unifi_to_hass_options.get(
                slot_str, PTZ_PATROL_STOP
            )
        else:
            # No patrol running - show Stop
            self._attr_current_option = PTZ_PATROL_STOP

    @callback
    def _async_update_device_from_protect(self, device: ProtectDeviceType) -> None:
        super()._async_update_device_from_protect(device)
        # Update patrol state from websocket updates
        if self.entity_description.key == _KEY_PTZ_PATROL:
            self._update_patrol_state()
        elif self.entity_description.key == _KEY_PTZ_PRESET:
            # Always reset preset to Idle - it's a command, not a state
            self._attr_current_option = PTZ_PRESET_IDLE

    @async_ufp_instance_command
    async def async_select_option(self, option: str) -> None:
        """Change the PTZ Select Entity Option."""
        unifi_value = self._hass_to_unifi_options.get(option)
        if unifi_value is None:
            return

        # Ignore selection of the Idle placeholder
        if unifi_value == PTZ_PRESET_IDLE:
            return

        if self.entity_description.ufp_set_method_fn is None:
            return
        await self.entity_description.ufp_set_method_fn(self.device, unifi_value)

        # Reset preset to Idle after command execution
        if self.entity_description.key == _KEY_PTZ_PRESET:
            # Set to selected option first, then schedule reset
            # This forces the frontend to see a state change
            self._attr_current_option = option
            self.async_write_ha_state()

            @callback
            def _reset_to_idle() -> None:
                """Reset preset to Idle after delay."""
                self._reset_timer = None
                self._attr_current_option = PTZ_PRESET_IDLE
                self.async_write_ha_state()

            # Cancel any existing timer before scheduling new one
            if self._reset_timer is not None:
                self._reset_timer.cancel()
            self._reset_timer = self.hass.loop.call_later(
                _PTZ_PRESET_RESET_DELAY, _reset_to_idle
            )
        # For patrols: State will be updated via websocket when active_patrol_slot changes
