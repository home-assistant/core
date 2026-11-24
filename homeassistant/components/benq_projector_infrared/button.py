"""Button platform for BenQ Projector Infrared integration."""

from dataclasses import dataclass
from typing import override

from infrared_protocols.codes.benq.projector import BenQProjectorCode

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BenQProjectorIrConfigEntry
from .entity import BenQProjectorIrEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class BenQProjectorIrButtonEntityDescription(ButtonEntityDescription):
    """Describes BenQ Projector Infrared button entity."""

    command_code: BenQProjectorCode


# Power, volume, mute and the inputs are controlled by the media player. Keys that
# not every projector has are disabled by default.
BUTTONS: tuple[BenQProjectorIrButtonEntityDescription, ...] = (
    BenQProjectorIrButtonEntityDescription(
        key="menu",
        translation_key="menu",
        command_code=BenQProjectorCode.MENU,
    ),
    BenQProjectorIrButtonEntityDescription(
        key="back",
        translation_key="back",
        command_code=BenQProjectorCode.BACK,
    ),
    BenQProjectorIrButtonEntityDescription(
        key="cursor_up",
        translation_key="cursor_up",
        command_code=BenQProjectorCode.UP,
    ),
    BenQProjectorIrButtonEntityDescription(
        key="cursor_down",
        translation_key="cursor_down",
        command_code=BenQProjectorCode.DOWN,
    ),
    BenQProjectorIrButtonEntityDescription(
        key="cursor_left",
        translation_key="cursor_left",
        command_code=BenQProjectorCode.LEFT,
    ),
    BenQProjectorIrButtonEntityDescription(
        key="cursor_right",
        translation_key="cursor_right",
        command_code=BenQProjectorCode.RIGHT,
    ),
    BenQProjectorIrButtonEntityDescription(
        key="enter",
        translation_key="enter",
        command_code=BenQProjectorCode.ENTER,
    ),
    BenQProjectorIrButtonEntityDescription(
        key="info",
        translation_key="info",
        command_code=BenQProjectorCode.INFO,
    ),
    BenQProjectorIrButtonEntityDescription(
        key="picture_mode",
        translation_key="picture_mode",
        command_code=BenQProjectorCode.PICTURE_MODE,
    ),
    BenQProjectorIrButtonEntityDescription(
        key="aspect_ratio",
        translation_key="aspect_ratio",
        command_code=BenQProjectorCode.ASPECT,
    ),
    BenQProjectorIrButtonEntityDescription(
        key="light_mode",
        translation_key="light_mode",
        command_code=BenQProjectorCode.LIGHT_MODE,
    ),
    BenQProjectorIrButtonEntityDescription(
        key="eco_blank",
        translation_key="eco_blank",
        command_code=BenQProjectorCode.ECO_BLANK,
    ),
    BenQProjectorIrButtonEntityDescription(
        key="return",
        translation_key="return",
        command_code=BenQProjectorCode.RETURN,
        entity_registry_enabled_default=False,
    ),
    BenQProjectorIrButtonEntityDescription(
        key="auto_adjust",
        translation_key="auto_adjust",
        command_code=BenQProjectorCode.AUTO,
        entity_registry_enabled_default=False,
    ),
    BenQProjectorIrButtonEntityDescription(
        key="freeze",
        translation_key="freeze",
        command_code=BenQProjectorCode.FREEZE,
        entity_registry_enabled_default=False,
    ),
    BenQProjectorIrButtonEntityDescription(
        key="user_1",
        translation_key="user_1",
        command_code=BenQProjectorCode.USER_1,
        entity_registry_enabled_default=False,
    ),
    BenQProjectorIrButtonEntityDescription(
        key="user_2",
        translation_key="user_2",
        command_code=BenQProjectorCode.USER_2,
        entity_registry_enabled_default=False,
    ),
    BenQProjectorIrButtonEntityDescription(
        key="user_3",
        translation_key="user_3",
        command_code=BenQProjectorCode.USER_3,
        entity_registry_enabled_default=False,
    ),
    BenQProjectorIrButtonEntityDescription(
        key="brightness",
        translation_key="brightness",
        command_code=BenQProjectorCode.BRIGHTNESS,
        entity_registry_enabled_default=False,
    ),
    BenQProjectorIrButtonEntityDescription(
        key="contrast",
        translation_key="contrast",
        command_code=BenQProjectorCode.CONTRAST,
        entity_registry_enabled_default=False,
    ),
    BenQProjectorIrButtonEntityDescription(
        key="color",
        translation_key="color",
        command_code=BenQProjectorCode.COLOR,
        entity_registry_enabled_default=False,
    ),
    BenQProjectorIrButtonEntityDescription(
        key="tint",
        translation_key="tint",
        command_code=BenQProjectorCode.TINT,
        entity_registry_enabled_default=False,
    ),
    BenQProjectorIrButtonEntityDescription(
        key="sharpness",
        translation_key="sharpness",
        command_code=BenQProjectorCode.SHARPNESS,
        entity_registry_enabled_default=False,
    ),
    BenQProjectorIrButtonEntityDescription(
        key="gamma",
        translation_key="gamma",
        command_code=BenQProjectorCode.GAMMA,
        entity_registry_enabled_default=False,
    ),
    BenQProjectorIrButtonEntityDescription(
        key="color_temperature",
        translation_key="color_temperature",
        command_code=BenQProjectorCode.COLOR_TEMPERATURE,
        entity_registry_enabled_default=False,
    ),
    BenQProjectorIrButtonEntityDescription(
        key="color_management",
        translation_key="color_management",
        command_code=BenQProjectorCode.COLOR_MANAGEMENT,
        entity_registry_enabled_default=False,
    ),
    BenQProjectorIrButtonEntityDescription(
        key="brilliant_color",
        translation_key="brilliant_color",
        command_code=BenQProjectorCode.BRILLIANT_COLOR,
        entity_registry_enabled_default=False,
    ),
    BenQProjectorIrButtonEntityDescription(
        key="detail_enhancement",
        translation_key="detail_enhancement",
        command_code=BenQProjectorCode.DETAIL_ENHANCEMENT,
        entity_registry_enabled_default=False,
    ),
    BenQProjectorIrButtonEntityDescription(
        key="fine_tune",
        translation_key="fine_tune",
        command_code=BenQProjectorCode.FINE_TUNE,
        entity_registry_enabled_default=False,
    ),
    BenQProjectorIrButtonEntityDescription(
        key="cinema_master",
        translation_key="cinema_master",
        command_code=BenQProjectorCode.CINEMA_MASTER,
        entity_registry_enabled_default=False,
    ),
    BenQProjectorIrButtonEntityDescription(
        key="dynamic_iris",
        translation_key="dynamic_iris",
        command_code=BenQProjectorCode.DYNAMIC_IRIS,
        entity_registry_enabled_default=False,
    ),
    BenQProjectorIrButtonEntityDescription(
        key="hdr",
        translation_key="hdr",
        command_code=BenQProjectorCode.HDR,
        entity_registry_enabled_default=False,
    ),
    BenQProjectorIrButtonEntityDescription(
        key="lumiexpert",
        translation_key="lumiexpert",
        command_code=BenQProjectorCode.LUMIEXPERT,
        entity_registry_enabled_default=False,
    ),
    BenQProjectorIrButtonEntityDescription(
        key="sound_mode",
        translation_key="sound_mode",
        command_code=BenQProjectorCode.SOUND_MODE,
        entity_registry_enabled_default=False,
    ),
    BenQProjectorIrButtonEntityDescription(
        key="overscan",
        translation_key="overscan",
        command_code=BenQProjectorCode.OVERSCAN,
        entity_registry_enabled_default=False,
    ),
    BenQProjectorIrButtonEntityDescription(
        key="aspect_ratio_anamorphic",
        translation_key="aspect_ratio_anamorphic",
        command_code=BenQProjectorCode.ASPECT_ANAMORPHIC,
        entity_registry_enabled_default=False,
    ),
    BenQProjectorIrButtonEntityDescription(
        key="aspect_ratio_4_3",
        translation_key="aspect_ratio_4_3",
        command_code=BenQProjectorCode.ASPECT_4_3,
        entity_registry_enabled_default=False,
    ),
    BenQProjectorIrButtonEntityDescription(
        key="aspect_ratio_letterbox",
        translation_key="aspect_ratio_letterbox",
        command_code=BenQProjectorCode.ASPECT_LETTERBOX,
        entity_registry_enabled_default=False,
    ),
    BenQProjectorIrButtonEntityDescription(
        key="aspect_ratio_wide",
        translation_key="aspect_ratio_wide",
        command_code=BenQProjectorCode.ASPECT_WIDE,
        entity_registry_enabled_default=False,
    ),
    BenQProjectorIrButtonEntityDescription(
        key="aspect_ratio_real",
        translation_key="aspect_ratio_real",
        command_code=BenQProjectorCode.ASPECT_REAL,
        entity_registry_enabled_default=False,
    ),
    BenQProjectorIrButtonEntityDescription(
        key="three_d",
        translation_key="three_d",
        command_code=BenQProjectorCode.THREE_D,
        entity_registry_enabled_default=False,
    ),
    BenQProjectorIrButtonEntityDescription(
        key="three_d_menu",
        translation_key="three_d_menu",
        command_code=BenQProjectorCode.THREE_D_MENU,
        entity_registry_enabled_default=False,
    ),
    BenQProjectorIrButtonEntityDescription(
        key="three_d_sync_invert",
        translation_key="three_d_sync_invert",
        command_code=BenQProjectorCode.THREE_D_SYNC_INVERT,
        entity_registry_enabled_default=False,
    ),
    BenQProjectorIrButtonEntityDescription(
        key="play",
        translation_key="play",
        command_code=BenQProjectorCode.PLAY,
        entity_registry_enabled_default=False,
    ),
    BenQProjectorIrButtonEntityDescription(
        key="pause",
        translation_key="pause",
        command_code=BenQProjectorCode.PAUSE,
        entity_registry_enabled_default=False,
    ),
    BenQProjectorIrButtonEntityDescription(
        key="stop",
        translation_key="stop",
        command_code=BenQProjectorCode.STOP,
        entity_registry_enabled_default=False,
    ),
    BenQProjectorIrButtonEntityDescription(
        key="previous_track",
        translation_key="previous_track",
        command_code=BenQProjectorCode.PREVIOUS,
        entity_registry_enabled_default=False,
    ),
    BenQProjectorIrButtonEntityDescription(
        key="next_track",
        translation_key="next_track",
        command_code=BenQProjectorCode.NEXT,
        entity_registry_enabled_default=False,
    ),
    BenQProjectorIrButtonEntityDescription(
        key="rewind",
        translation_key="rewind",
        command_code=BenQProjectorCode.REWIND,
        entity_registry_enabled_default=False,
    ),
    BenQProjectorIrButtonEntityDescription(
        key="fast_forward",
        translation_key="fast_forward",
        command_code=BenQProjectorCode.FAST_FORWARD,
        entity_registry_enabled_default=False,
    ),
    BenQProjectorIrButtonEntityDescription(
        key="keystone_up",
        translation_key="keystone_up",
        command_code=BenQProjectorCode.KEYSTONE_UP,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
    BenQProjectorIrButtonEntityDescription(
        key="keystone_down",
        translation_key="keystone_down",
        command_code=BenQProjectorCode.KEYSTONE_DOWN,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
    BenQProjectorIrButtonEntityDescription(
        key="keystone_2d",
        translation_key="keystone_2d",
        command_code=BenQProjectorCode.KEYSTONE_2D,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
    BenQProjectorIrButtonEntityDescription(
        key="keystone_vertical",
        translation_key="keystone_vertical",
        command_code=BenQProjectorCode.KEYSTONE_VERTICAL,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
    BenQProjectorIrButtonEntityDescription(
        key="keystone_horizontal",
        translation_key="keystone_horizontal",
        command_code=BenQProjectorCode.KEYSTONE_HORIZONTAL,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
    BenQProjectorIrButtonEntityDescription(
        key="digital_zoom_in",
        translation_key="digital_zoom_in",
        command_code=BenQProjectorCode.DIGITAL_ZOOM_IN,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
    BenQProjectorIrButtonEntityDescription(
        key="digital_zoom_out",
        translation_key="digital_zoom_out",
        command_code=BenQProjectorCode.DIGITAL_ZOOM_OUT,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
    BenQProjectorIrButtonEntityDescription(
        key="lens",
        translation_key="lens",
        command_code=BenQProjectorCode.LENS,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
    BenQProjectorIrButtonEntityDescription(
        key="focus",
        translation_key="focus",
        command_code=BenQProjectorCode.FOCUS,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
    BenQProjectorIrButtonEntityDescription(
        key="zoom",
        translation_key="zoom",
        command_code=BenQProjectorCode.ZOOM,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
    BenQProjectorIrButtonEntityDescription(
        key="pan",
        translation_key="pan",
        command_code=BenQProjectorCode.PAN,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
    BenQProjectorIrButtonEntityDescription(
        key="test_pattern",
        translation_key="test_pattern",
        command_code=BenQProjectorCode.TEST_PATTERN,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BenQProjectorIrConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up BenQ Projector Infrared buttons from config entry."""
    async_add_entities(
        BenQProjectorIrButton(entry, description) for description in BUTTONS
    )


class BenQProjectorIrButton(BenQProjectorIrEntity, ButtonEntity):
    """BenQ Projector Infrared button entity."""

    entity_description: BenQProjectorIrButtonEntityDescription

    def __init__(
        self,
        entry: BenQProjectorIrConfigEntry,
        description: BenQProjectorIrButtonEntityDescription,
    ) -> None:
        """Initialize BenQ Projector Infrared button."""
        super().__init__(entry, unique_id_suffix=description.key)
        self.entity_description = description

    @override
    async def async_press(self) -> None:
        """Press the button."""
        await self._send_benq_command(self.entity_description.command_code)
