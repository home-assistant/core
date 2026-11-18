"""Support for the numeric image settings of Hikvision cameras."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, override

from pyhik.image import ImageSetting, ImageSettingType

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HikvisionConfigEntry
from .const import DOMAIN
from .coordinator import HikvisionImageCoordinator
from .entity import HikvisionImageEntity

# All writes to a camera are serialized by the coordinator.
PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class HikvisionNumberEntityDescription(NumberEntityDescription):
    """Describes a Hikvision image setting number."""

    # Matched case-insensitively: some firmware spells the same path differently.
    path: str


NUMBER_DESCRIPTIONS: tuple[HikvisionNumberEntityDescription, ...] = (
    HikvisionNumberEntityDescription(
        key="brightness",
        translation_key="brightness",
        path="Color/brightnessLevel",
        entity_category=EntityCategory.CONFIG,
    ),
    HikvisionNumberEntityDescription(
        key="contrast",
        translation_key="contrast",
        path="Color/contrastLevel",
        entity_category=EntityCategory.CONFIG,
    ),
    HikvisionNumberEntityDescription(
        key="saturation",
        translation_key="saturation",
        path="Color/saturationLevel",
        entity_category=EntityCategory.CONFIG,
    ),
    HikvisionNumberEntityDescription(
        key="sharpness",
        translation_key="sharpness",
        path="Sharpness/SharpnessLevel",
        entity_category=EntityCategory.CONFIG,
    ),
    HikvisionNumberEntityDescription(
        key="gain",
        translation_key="gain",
        path="Gain/GainLevel",
        entity_category=EntityCategory.CONFIG,
    ),
    HikvisionNumberEntityDescription(
        key="gain_limit",
        translation_key="gain_limit",
        path="Gain/GainLimit",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
    HikvisionNumberEntityDescription(
        key="shutter_speed",
        translation_key="shutter_speed",
        path="Shutter/ShutterLevel",
        entity_category=EntityCategory.CONFIG,
    ),
    HikvisionNumberEntityDescription(
        key="wdr_level",
        translation_key="wdr_level",
        path="WDR/WDRLevel",
        entity_category=EntityCategory.CONFIG,
    ),
    HikvisionNumberEntityDescription(
        key="highlight_compensation_level",
        translation_key="highlight_compensation_level",
        path="HLC/HLCLevel",
        entity_category=EntityCategory.CONFIG,
    ),
    HikvisionNumberEntityDescription(
        key="night_to_day_sensitivity",
        translation_key="night_to_day_sensitivity",
        path="IrcutFilter/nightToDayFilterLevel",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
    HikvisionNumberEntityDescription(
        key="night_to_day_delay",
        translation_key="night_to_day_delay",
        path="IrcutFilter/nightToDayFilterTime",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
    HikvisionNumberEntityDescription(
        key="auto_iris_level",
        translation_key="auto_iris_level",
        path="Exposure/autoIrisLevel",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
    HikvisionNumberEntityDescription(
        key="p_iris_level",
        translation_key="p_iris_level",
        path="Exposure/pIris/IrisLevel",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
    HikvisionNumberEntityDescription(
        key="max_iris_level",
        translation_key="max_iris_level",
        path="Iris/maxIrisLevelLimit",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
    HikvisionNumberEntityDescription(
        key="min_iris_level",
        translation_key="min_iris_level",
        path="Iris/minIrisLevelLimit",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
    HikvisionNumberEntityDescription(
        key="white_balance_red",
        translation_key="white_balance_red",
        path="WhiteBalance/WhiteBalanceRed",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
    HikvisionNumberEntityDescription(
        key="white_balance_blue",
        translation_key="white_balance_blue",
        path="WhiteBalance/WhiteBalanceBlue",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
    HikvisionNumberEntityDescription(
        key="noise_reduction_level",
        translation_key="noise_reduction_level",
        path="NoiseReduce/GeneralMode/generalLevel",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
    HikvisionNumberEntityDescription(
        key="spatial_noise_reduction_level",
        translation_key="spatial_noise_reduction_level",
        path="NoiseReduce/AdvancedMode/FrameNoiseReduceLevel",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
    HikvisionNumberEntityDescription(
        key="temporal_noise_reduction_level",
        translation_key="temporal_noise_reduction_level",
        path="NoiseReduce/AdvancedMode/InterFrameNoiseReduceLevel",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
    HikvisionNumberEntityDescription(
        key="smart_noise_reduction_level",
        translation_key="smart_noise_reduction_level",
        path="smartNoiseReduce/level",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
    HikvisionNumberEntityDescription(
        key="defog_level",
        translation_key="defog_level",
        path="Dehaze/DehazeLevel",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
    HikvisionNumberEntityDescription(
        key="smart_supplement_light_distance",
        translation_key="smart_supplement_light_distance",
        path="Exposure/OverexposeSuppress/DistanceLevel",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
    HikvisionNumberEntityDescription(
        key="smart_supplement_light_high_light_distance",
        translation_key="smart_supplement_light_high_light_distance",
        path="Exposure/OverexposeSuppress/hightLightDistanceLevel",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
    HikvisionNumberEntityDescription(
        key="smart_supplement_light_low_light_distance",
        translation_key="smart_supplement_light_low_light_distance",
        path="Exposure/OverexposeSuppress/lowLightDistanceLevel",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
    HikvisionNumberEntityDescription(
        key="light_brightness",
        translation_key="light_brightness",
        path="SupplementLight/whiteLightBrightness",
        entity_category=EntityCategory.CONFIG,
    ),
    HikvisionNumberEntityDescription(
        key="white_light_brightness_limit",
        translation_key="white_light_brightness_limit",
        path="SupplementLight/whiteLightbrightnessLimit",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
    HikvisionNumberEntityDescription(
        key="ir_light_brightness",
        translation_key="ir_light_brightness",
        path="SupplementLight/irLightBrightness",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
    HikvisionNumberEntityDescription(
        key="ir_light_brightness_limit",
        translation_key="ir_light_brightness_limit",
        path="SupplementLight/irLightbrightnessLimit",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
    HikvisionNumberEntityDescription(
        key="ir_high_brightness",
        translation_key="ir_high_brightness",
        path="SupplementLight/highIrLightBrightness",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
    HikvisionNumberEntityDescription(
        key="ir_low_brightness",
        translation_key="ir_low_brightness",
        path="SupplementLight/lowIrLightBrightness",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
    HikvisionNumberEntityDescription(
        key="ir_brightness_limit",
        translation_key="ir_brightness_limit",
        path="IrLight/brightnessLimit",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
    HikvisionNumberEntityDescription(
        key="event_intelligence_white_light_brightness",
        translation_key="event_intelligence_white_light_brightness",
        path="SupplementLight/EventIntelligenceModeCfg/whiteLightBrightness",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
    HikvisionNumberEntityDescription(
        key="event_intelligence_ir_light_brightness",
        translation_key="event_intelligence_ir_light_brightness",
        path="SupplementLight/EventIntelligenceModeCfg/irLightBrightness",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
    HikvisionNumberEntityDescription(
        key="lens_distortion_correction_level",
        translation_key="lens_distortion_correction_level",
        path="LensDistortionCorrection/accurateLevel",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
)

_DESCRIPTIONS_BY_PATH = {
    description.path.lower(): description for description in NUMBER_DESCRIPTIONS
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HikvisionConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Hikvision image setting numbers."""
    coordinator = entry.runtime_data.image_coordinator
    if coordinator is None:
        return

    async_add_entities(
        HikvisionImageNumber(coordinator, entry, description, setting)
        for setting in coordinator.settings
        if setting.type is ImageSettingType.NUMBER
        # Without both ends of the range there is no slider to show.
        and setting.min_value is not None
        and setting.max_value is not None
        and (description := _DESCRIPTIONS_BY_PATH.get(setting.path.lower()))
    )


class HikvisionImageNumber(HikvisionImageEntity, NumberEntity):
    """A number for a ranged image setting."""

    entity_description: HikvisionNumberEntityDescription
    _attr_native_step = 1

    def __init__(
        self,
        coordinator: HikvisionImageCoordinator,
        entry: HikvisionConfigEntry,
        description: HikvisionNumberEntityDescription,
        setting: ImageSetting,
    ) -> None:
        """Initialize the number."""
        super().__init__(coordinator, entry, setting.path)
        self.entity_description = description
        # The setup only creates a number for a setting that has a range.
        if TYPE_CHECKING:
            assert setting.min_value is not None
            assert setting.max_value is not None
        self._attr_native_min_value = setting.min_value
        self._attr_native_max_value = setting.max_value

    @property
    @override
    def native_value(self) -> float | None:
        """Return the current value."""
        if (value := self._value) is None:
            return None
        try:
            return float(value)
        except ValueError:
            return None

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Set a new value."""
        if value != int(value):
            # The camera takes whole numbers: rounding would change the value silently.
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="image_setting_not_whole",
            )
        await self.coordinator.async_set_setting(self._path, str(int(value)))
