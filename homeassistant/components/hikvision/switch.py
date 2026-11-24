"""Support for the image setting and detection switches of Hikvision cameras."""

from dataclasses import dataclass
from typing import Any, override

from pyhik.image import ImageSettingType

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HikvisionConfigEntry
from .const import DETECTION_KEYS, IMAGE_SWITCH_SETTINGS
from .coordinator import HikvisionImageCoordinator, detection_path
from .entity import HikvisionImageEntity

# All writes to a camera are serialized by the coordinator.
PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class HikvisionSwitchEntityDescription(SwitchEntityDescription):
    """Describes a Hikvision image setting switch."""

    # Matched case-insensitively: some firmware spells the same path differently.
    path: str


SWITCH_DESCRIPTIONS: tuple[HikvisionSwitchEntityDescription, ...] = tuple(
    HikvisionSwitchEntityDescription(
        key=setting.key,
        translation_key=setting.key,
        path=setting.path,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=setting.enabled_by_default,
    )
    for setting in IMAGE_SWITCH_SETTINGS
)

_DESCRIPTIONS_BY_PATH = {
    description.path.lower(): description for description in SWITCH_DESCRIPTIONS
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HikvisionConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Hikvision image setting and detection switches."""
    coordinators = entry.runtime_data.image_coordinators
    entities: list[HikvisionImageSwitch] = [
        HikvisionImageSwitch(coordinator, entry, description, setting.path)
        for coordinator in coordinators
        for setting in coordinator.settings
        if setting.type is ImageSettingType.SWITCH
        and (description := _DESCRIPTIONS_BY_PATH.get(setting.path.lower()))
    ]
    # Only the detections the camera has: its first poll found them.
    entities.extend(
        HikvisionDetectionSwitch(coordinator, entry, detection)
        for coordinator in coordinators
        for detection in coordinator.detections or ()
        if detection in DETECTION_KEYS
    )
    async_add_entities(entities)


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
        """Return true if the setting is on.

        A value other than true or false says nothing about the setting: unknown.
        """
        if (value := self._value) is None:
            return None
        return {"true": True, "false": False}.get(value.lower())

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the setting on."""
        await self.coordinator.async_set_setting(self._path, "true", self._context)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the setting off."""
        await self.coordinator.async_set_setting(self._path, "false", self._context)


class HikvisionDetectionSwitch(HikvisionImageSwitch):
    """A switch to turn a detection of the camera on or off."""

    def __init__(
        self,
        coordinator: HikvisionImageCoordinator,
        entry: HikvisionConfigEntry,
        detection: str,
    ) -> None:
        """Initialize the switch."""
        key = DETECTION_KEYS[detection]
        super().__init__(
            coordinator,
            entry,
            HikvisionSwitchEntityDescription(
                key=key,
                translation_key=key,
                path=detection_path(detection),
                # No entity category: controls, turned on and off by hand or by
                # automations, apart from the image settings.
            ),
            detection_path(detection),
        )
        self._detection = detection
        # Not an image setting: its own unique ID, from the key.
        self._attr_unique_id = f"{coordinator.device_unique_id_prefix}{key}"

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the detection on."""
        await self.coordinator.async_set_detection(self._detection, True, self._context)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the detection off."""
        await self.coordinator.async_set_detection(
            self._detection, False, self._context
        )
