"""Writable video and detection settings for reCamera Pro."""

from dataclasses import dataclass
import math
from typing import Any

from recamera_protocol import (
    ALL_MOTION_OPTION_SPECS,
    MAX_GOP,
    RecameraError,
    RecameraValidationError,
    bitrate_range,
    max_frame_rate,
)

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity_registry import RegistryEntryHider

from .const import (
    CONF_AUDIO_CONFIDENCE,
    CONF_AUDIO_COOLDOWN,
    CONF_CLASS_STALE_SECONDS,
    CONF_VISUAL_CONFIDENCE,
    CONF_VISUAL_CONFIRM,
    CONF_VISUAL_COOLDOWN,
    DOMAIN,
    SOURCE_AVAILABLE,
)
from .coordinator import RecameraCoordinator
from .entity import RecameraEntity, recamera_service_error

PARALLEL_UPDATES = 0
MAIN_BITRATE_MIN, MAIN_BITRATE_MAX = bitrate_range(0) or (256, 16384)
SUB_BITRATE_MIN, SUB_BITRATE_MAX = bitrate_range(1) or (128, 4096)


@dataclass(frozen=True, kw_only=True)
class RecameraNumberDescription(NumberEntityDescription):
    """Description for one writable setting."""

    key: str
    minimum: float
    maximum: float
    step_size: float
    unit: str | None = None
    stream: str | None = None
    section: str | None = None
    field: str | None = None
    option_key: str | None = None
    multiplier: float = 1


VIDEO_DESCRIPTIONS = (
    RecameraNumberDescription(
        key="main_max_bitrate",
        stream="main",
        field="iMaxRate",
        minimum=MAIN_BITRATE_MIN,
        maximum=MAIN_BITRATE_MAX,
        step_size=256,
        unit="kbit/s",
    ),
    RecameraNumberDescription(
        key="sub_max_bitrate",
        stream="sub",
        field="iMaxRate",
        minimum=SUB_BITRATE_MIN,
        maximum=SUB_BITRATE_MAX,
        step_size=128,
        unit="kbit/s",
    ),
    RecameraNumberDescription(
        key="main_frame_rate",
        stream="main",
        field="sFrameRate",
        minimum=1,
        maximum=60,
        step_size=1,
        unit="fps",
    ),
    RecameraNumberDescription(
        key="sub_frame_rate",
        stream="sub",
        field="sFrameRate",
        minimum=1,
        maximum=30,
        step_size=1,
        unit="fps",
    ),
    RecameraNumberDescription(
        key="main_gop",
        stream="main",
        field="iGOP",
        minimum=1,
        maximum=MAX_GOP,
        step_size=1,
    ),
    RecameraNumberDescription(
        key="sub_gop",
        stream="sub",
        field="iGOP",
        minimum=1,
        maximum=MAX_GOP,
        step_size=1,
    ),
)

DETECTION_DESCRIPTIONS = (
    RecameraNumberDescription(
        key="yolo_confidence",
        option_key=CONF_VISUAL_CONFIDENCE,
        minimum=0.0,
        maximum=1.0,
        step_size=0.01,
    ),
    RecameraNumberDescription(
        key="yolo_confirm_seconds",
        option_key=CONF_VISUAL_CONFIRM,
        minimum=0,
        maximum=30,
        step_size=0.1,
        unit="s",
    ),
    RecameraNumberDescription(
        key="yolo_hold_seconds",
        option_key=CONF_CLASS_STALE_SECONDS,
        minimum=1,
        maximum=60,
        step_size=1,
        unit="s",
    ),
    RecameraNumberDescription(
        key="yolo_cooldown_seconds",
        option_key=CONF_VISUAL_COOLDOWN,
        minimum=0,
        maximum=60,
        step_size=1,
        unit="s",
    ),
    RecameraNumberDescription(
        key="sound_confidence",
        option_key=CONF_AUDIO_CONFIDENCE,
        minimum=0.0,
        maximum=1.0,
        step_size=0.01,
    ),
    RecameraNumberDescription(
        key="sound_cooldown_seconds",
        option_key=CONF_AUDIO_COOLDOWN,
        minimum=0,
        maximum=60,
        step_size=1,
        unit="s",
    ),
    RecameraNumberDescription(
        key="motion_sq_diff_threshold",
        field="sq_diff_threshold",
        minimum=1,
        maximum=65025,
        step_size=1,
    ),
    RecameraNumberDescription(
        key="motion_min_changed_ratio",
        field="min_changed_ratio",
        minimum=0,
        maximum=0.5,
        step_size=0.001,
    ),
    RecameraNumberDescription(
        key="motion_hold_seconds",
        field="motion_hold_ms",
        minimum=0,
        maximum=60,
        step_size=0.1,
        unit="s",
        multiplier=1000,
    ),
    RecameraNumberDescription(
        key="motion_sample_fps",
        field="sample_fps",
        minimum=0.2,
        maximum=30,
        step_size=0.1,
        unit="fps",
    ),
)

MOTION_SPECS = {spec.key: spec for spec in ALL_MOTION_OPTION_SPECS}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up video and detection settings."""
    coordinator: RecameraCoordinator = config_entry.runtime_data
    created: set[str] = set()

    def add_supported_entities() -> None:
        new_entities: list[NumberEntity] = []
        for description in VIDEO_DESCRIPTIONS:
            if description.key in created or not _video_number_is_supported(
                coordinator, description
            ):
                continue
            created.add(description.key)
            new_entities.append(RecameraVideoNumber(coordinator, description))
        for description in DETECTION_DESCRIPTIONS:
            if description.key in created or not _detection_number_is_supported(
                coordinator, description
            ):
                continue
            created.add(description.key)
            new_entities.append(RecameraDetectionNumber(coordinator, description))
        if new_entities:
            async_add_entities(new_entities)
            _sync_number_visibility(hass, coordinator)

    add_supported_entities()
    config_entry.async_on_unload(coordinator.async_add_listener(add_supported_entities))
    _sync_number_visibility(hass, coordinator)


def _numeric_value(value: object) -> float | None:
    """Return a finite numeric value from an API field."""
    if not isinstance(value, (int, float, str)):
        return None
    try:
        number = float(value)
    except TypeError, ValueError:
        return None
    return number if math.isfinite(number) else None


def _video_number_is_supported(
    coordinator: RecameraCoordinator,
    description: RecameraNumberDescription,
) -> bool:
    """Return whether the stream encoding exposes this numeric field."""
    data = getattr(coordinator, "data", None)
    media_profiles = getattr(data, "media_profiles", {})
    encode = media_profiles.get(description.stream or "", {}).get("encode") or {}
    return _numeric_value(encode.get(description.field)) is not None


def _detection_number_is_supported(
    coordinator: RecameraCoordinator,
    description: RecameraNumberDescription,
) -> bool:
    """Return whether this local or device setting is currently available."""
    if description.option_key is not None:
        return True
    data = getattr(coordinator, "data", None)
    motion = getattr(data, "motion", None)
    if motion is None:
        return False
    return bool(
        motion.installed
        and _numeric_value(motion.config.get(description.field)) is not None
    )


def _number_visibility_is_supported(
    coordinator: RecameraCoordinator,
    description: RecameraNumberDescription,
) -> bool:
    """Keep existing controls visible while capability data is temporarily absent."""
    if getattr(coordinator, "data", None) is None:
        return True
    if description.option_key is not None:
        return True
    if description.field is not None and description.stream is not None:
        return _video_number_is_supported(coordinator, description)
    return _detection_number_is_supported(coordinator, description)


def _validated_integer(
    value: float,
    minimum: float,
    maximum: float,
    error_key: str,
) -> int:
    """Return a bounded integer or reject a direct service call."""
    numeric = float(value)
    if not numeric.is_integer() or not minimum <= numeric <= maximum:
        raise RecameraValidationError(error_key)
    return int(numeric)


class RecameraVideoNumber(RecameraEntity, NumberEntity):
    """Representation of one video encoding number."""

    entity_description: RecameraNumberDescription
    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = NumberMode.BOX
    _attr_should_poll = False

    def __init__(
        self,
        coordinator: RecameraCoordinator,
        description: RecameraNumberDescription,
    ) -> None:
        """Initialize one video number."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_translation_key = description.key
        self._attr_native_min_value = description.minimum
        self._attr_native_max_value = description.maximum
        self._attr_native_step = description.step_size
        self._attr_native_unit_of_measurement = description.unit
        self._attr_unique_id = f"{coordinator.device_id}_{description.key}"

    @property
    def _encode(self) -> dict[str, Any]:
        """Return current video encoding metadata."""
        profile = (
            self.coordinator.data.media_profiles.get(
                self.entity_description.stream or ""
            )
            or {}
        )
        encode = profile.get("encode")
        return dict(encode) if isinstance(encode, dict) else {}

    @property
    def available(self) -> bool:
        """Require current encoding metadata."""
        value = self.native_value
        return bool(
            super().available
            and value is not None
            and self.native_min_value <= value <= self.native_max_value
        )

    @property
    def native_value(self) -> float | None:
        """Return the current encoding value."""
        field = self.entity_description.field
        if field is None:
            return None
        value = self._encode.get(field)
        if not isinstance(value, (int, float, str)):
            return None
        try:
            return float(value)
        except TypeError, ValueError:
            return None

    @property
    def native_max_value(self) -> float:
        """Return the firmware limit for the current resolution."""
        description = self.entity_description
        if description.field == "sFrameRate":
            stream_id = 0 if description.stream == "main" else 1
            resolution = str(
                self._encode.get("sResolution")
                or ("3840*2160" if stream_id == 0 else "1280*720")
            )
            return float(max_frame_rate(stream_id, resolution))
        return description.maximum

    async def async_set_native_value(self, value: float) -> None:
        """Write one validated video setting."""
        try:
            field = self.entity_description.field
            max_bitrate: int | None = None
            gop: int | None = None
            frame_rate: str | None = None
            if field == "iMaxRate":
                max_bitrate = _validated_integer(
                    value,
                    self.entity_description.minimum,
                    self.entity_description.maximum,
                    "invalid_video_bitrate",
                )
            elif field == "iGOP":
                gop = _validated_integer(
                    value,
                    self.entity_description.minimum,
                    self.entity_description.maximum,
                    "invalid_video_gop",
                )
            elif field == "sFrameRate":
                frame_rate = str(
                    _validated_integer(
                        value,
                        self.entity_description.minimum,
                        self.native_max_value,
                        "invalid_video_frame_rate",
                    )
                )
            await self.coordinator.async_update_video_encode(
                self.entity_description.stream or "sub",
                max_bitrate=max_bitrate,
                gop=gop,
                frame_rate=frame_rate,
            )
        except RecameraError as err:
            raise recamera_service_error(err) from err


class RecameraDetectionNumber(RecameraEntity, NumberEntity):
    """Representation of one visual, sound, or motion setting."""

    entity_description: RecameraNumberDescription
    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = NumberMode.BOX
    _attr_should_poll = False

    def __init__(
        self,
        coordinator: RecameraCoordinator,
        description: RecameraNumberDescription,
    ) -> None:
        """Initialize one detection setting."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_translation_key = description.key
        self._attr_native_min_value = description.minimum
        self._attr_native_max_value = description.maximum
        self._attr_native_step = description.step_size
        self._attr_native_unit_of_measurement = description.unit
        self._attr_unique_id = f"{coordinator.device_id}_{description.key}"

    @property
    def available(self) -> bool:
        """Require the motion App for motion settings."""
        if self.entity_description.field is None:
            return super().available
        motion = self.coordinator.data.motion
        return (
            super().available
            and motion.installed
            and motion.app_health == SOURCE_AVAILABLE
            and motion.config_health == SOURCE_AVAILABLE
            and _numeric_value(motion.config.get(self.entity_description.field))
            is not None
        )

    @property
    def native_value(self) -> float | None:
        """Return the current integration or motion App value."""
        option_key = self.entity_description.option_key
        if option_key == CONF_VISUAL_CONFIDENCE:
            return self.coordinator.visual_min_confidence
        if option_key == CONF_VISUAL_CONFIRM:
            return self.coordinator.visual_confirm_seconds
        if option_key == CONF_AUDIO_CONFIDENCE:
            return self.coordinator.audio_min_confidence
        if option_key == CONF_CLASS_STALE_SECONDS:
            return self.coordinator.class_stale_seconds
        if option_key == CONF_VISUAL_COOLDOWN:
            return self.coordinator.visual_cooldown
        if option_key == CONF_AUDIO_COOLDOWN:
            return self.coordinator.audio_cooldown
        field = self.entity_description.field
        if field is None:
            return None
        try:
            value = float(self.coordinator.data.motion.config[field])
        except KeyError, TypeError, ValueError:
            return None
        return value / self.entity_description.multiplier

    async def async_set_native_value(self, value: float) -> None:
        """Write one validated detection setting."""
        try:
            if self.entity_description.option_key is not None:
                await self.coordinator.async_set_detection_option(
                    self.entity_description.option_key,
                    float(value),
                )
                return
            field = self.entity_description.field
            if field is None:
                return
            spec = MOTION_SPECS[field]
            try:
                raw_value = value * self.entity_description.multiplier
                if spec.integer:
                    raw_value = round(raw_value)
                coerced = spec.coerce(raw_value)
            except (TypeError, ValueError) as err:
                raise RecameraValidationError("invalid_motion_config") from err
            config = {field: coerced}
            await self.coordinator.async_update_motion_detection_config(config)
        except RecameraError as err:
            raise recamera_service_error(err) from err


def _sync_number_visibility(
    hass: HomeAssistant,
    coordinator: RecameraCoordinator,
) -> None:
    """Unhide current settings while preserving user-hidden entries."""
    registry = er.async_get(hass)
    kept = {
        f"{coordinator.device_id}_{description.key}"
        for description in VIDEO_DESCRIPTIONS
        if _number_visibility_is_supported(coordinator, description)
    }
    kept.update(
        f"{coordinator.device_id}_{description.key}"
        for description in DETECTION_DESCRIPTIONS
        if _number_visibility_is_supported(coordinator, description)
    )
    for entry in list(registry.entities.values()):
        if (
            entry.platform != DOMAIN
            or entry.config_entry_id != coordinator.config_entry.entry_id
            or not str(entry.entity_id).startswith("number.")
            or entry.hidden_by == RegistryEntryHider.USER
        ):
            continue
        if entry.unique_id in kept:
            desired_hidden = None
        else:
            desired_hidden = RegistryEntryHider.INTEGRATION
        if entry.hidden_by != desired_hidden:
            registry.async_update_entity(
                entry.entity_id,
                hidden_by=desired_hidden,
            )
