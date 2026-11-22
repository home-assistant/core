"""Support for the image setting switches of Hikvision cameras."""

from dataclasses import dataclass
from typing import Any, override

from pyhik.image import ImageSettingType

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HikvisionConfigEntry
from .const import IMAGE_SWITCH_SETTINGS
from .coordinator import HikvisionImageCoordinator
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
        """Return true if the setting is on.

        A value other than true or false says nothing about the setting: unknown.
        """
        if (value := self._value) is None:
            return None
        return {"true": True, "false": False}.get(value.lower())

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the setting on."""
        await self.coordinator.async_set_setting(self._path, "true")

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the setting off."""
        await self.coordinator.async_set_setting(self._path, "false")
