"""Button platform for IronOS integration."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from pynecil import CharSetting

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import IronOSConfigEntry
from .coordinator import IronOSCoordinators
from .entity import IronOSBaseEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class IronOSButtonEntityDescription(ButtonEntityDescription):
    """Describes IronOS button entity."""

    characteristic: CharSetting


class IronOSButton(StrEnum):
    """Button controls for IronOS device."""

    SETTINGS_RESET = "settings_reset"
    SETTINGS_SAVE = "settings_save"


BUTTON_DESCRIPTIONS: tuple[IronOSButtonEntityDescription, ...] = (
    IronOSButtonEntityDescription(
        key=IronOSButton.SETTINGS_RESET,
        translation_key=IronOSButton.SETTINGS_RESET,
        characteristic=CharSetting.SETTINGS_RESET,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.CONFIG,
    ),
    IronOSButtonEntityDescription(
        key=IronOSButton.SETTINGS_SAVE,
        translation_key=IronOSButton.SETTINGS_SAVE,
        characteristic=CharSetting.SETTINGS_SAVE,
        entity_category=EntityCategory.CONFIG,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IronOSConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up button entities from a config entry."""
    coordinators = entry.runtime_data

    async_add_entities(
        IronOSButtonEntity(coordinators, description)
        for description in BUTTON_DESCRIPTIONS
    )


class IronOSButtonEntity(IronOSBaseEntity, ButtonEntity):
    """Implementation of a IronOS button entity."""

    entity_description: IronOSButtonEntityDescription

    def __init__(
        self,
        coordinators: IronOSCoordinators,
        entity_description: IronOSButtonEntityDescription,
    ) -> None:
        """Initialize the select entity."""
        super().__init__(coordinators.live_data, entity_description)

        self.settings = coordinators.settings

    async def async_press(self) -> None:
        """Handle the button press."""

        await self.settings.write(self.entity_description.characteristic, True)
