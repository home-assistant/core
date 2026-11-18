"""Support for the image setting switches of Hikvision cameras."""

from dataclasses import dataclass
from typing import Any, override

from pyhik.image import ImageSettingType

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HikvisionConfigEntry
from .coordinator import HikvisionImageCoordinator
from .entity import HikvisionImageEntity

# All writes to a camera are serialized by the coordinator.
PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class HikvisionSwitchEntityDescription(SwitchEntityDescription):
    """Describes a Hikvision image setting switch."""

    # Matched case-insensitively: some firmware spells the same path differently.
    path: str


SWITCH_DESCRIPTIONS: tuple[HikvisionSwitchEntityDescription, ...] = (
    # Only a camera that has the flag without a mode to go with it gets this one: pyHik
    # folds the flag into the mode, which is then a select.
    HikvisionSwitchEntityDescription(
        key="backlight_compensation",
        translation_key="backlight_compensation",
        path="BLC/enabled",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
    HikvisionSwitchEntityDescription(
        key="highlight_compensation",
        translation_key="highlight_compensation",
        path="HLC/enabled",
        entity_category=EntityCategory.CONFIG,
    ),
    HikvisionSwitchEntityDescription(
        key="smart_supplement_light",
        translation_key="smart_supplement_light",
        path="Exposure/OverexposeSuppress/enabled",
        entity_category=EntityCategory.CONFIG,
    ),
    HikvisionSwitchEntityDescription(
        key="image_flip",
        translation_key="image_flip",
        path="ImageFlip/enabled",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
    HikvisionSwitchEntityDescription(
        key="lens_distortion_correction",
        translation_key="lens_distortion_correction",
        path="LensDistortionCorrection/enabled",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
    HikvisionSwitchEntityDescription(
        key="image_stabilization",
        translation_key="image_stabilization",
        path="EIS/enabled",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
    HikvisionSwitchEntityDescription(
        key="digital_slow_shutter",
        translation_key="digital_slow_shutter",
        path="DSS/enabled",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
    HikvisionSwitchEntityDescription(
        key="image_freeze",
        translation_key="image_freeze",
        path="ImageFreeze/enabled",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
    HikvisionSwitchEntityDescription(
        key="lens_initialization",
        translation_key="lens_initialization",
        path="LensInitialization/enabled",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
    HikvisionSwitchEntityDescription(
        key="proportional_pan",
        translation_key="proportional_pan",
        path="proportionalpan/enabled",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
    HikvisionSwitchEntityDescription(
        key="image_loss_detection",
        translation_key="image_loss_detection",
        path="enableImageLossDetection",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
)

_DESCRIPTIONS_BY_PATH = {
    description.path.lower(): description for description in SWITCH_DESCRIPTIONS
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HikvisionConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Hikvision image setting switches."""
    coordinator = entry.runtime_data.image_coordinator
    if coordinator is None:
        return

    async_add_entities(
        HikvisionImageSwitch(coordinator, entry, description, setting.path)
        for setting in coordinator.settings
        if setting.type is ImageSettingType.SWITCH
        and (description := _DESCRIPTIONS_BY_PATH.get(setting.path.lower()))
    )


class HikvisionImageSwitch(HikvisionImageEntity, SwitchEntity):
    """A switch for an on/off image setting."""

    entity_description: HikvisionSwitchEntityDescription

    def __init__(
        self,
        coordinator: HikvisionImageCoordinator,
        entry: HikvisionConfigEntry,
        description: HikvisionSwitchEntityDescription,
        path: str,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, entry, description, path)

    @property
    @override
    def is_on(self) -> bool | None:
        """Return true if the setting is on."""
        if (value := self._value) is None:
            return None
        return value.lower() == "true"

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the setting on."""
        await self.coordinator.async_set_setting(self._path, "true")

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the setting off."""
        await self.coordinator.async_set_setting(self._path, "false")
