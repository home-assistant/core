"""Button platform for IronOS integration."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from pynecil import CharSetting, CommunicationError, Pynecil

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import IronOSConfigEntry
from .const import DOMAIN
from .coordinator import IronOSCoordinators
from .entity import IronOSBaseEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class IronOSButtonEntityDescription(ButtonEntityDescription):
    """Describes IronOS button entity."""

    press_fn: Callable[[Pynecil], Awaitable[Any]]


class IronOSButton(StrEnum):
    """Button controls for IronOS device."""

    SETTINGS_RESET = "settings_reset"
    SETTINGS_SAVE = "settings_save"
    BLE_ENABLED = "ble_enabled"


BUTTON_DESCRIPTIONS: tuple[IronOSButtonEntityDescription, ...] = (
    IronOSButtonEntityDescription(
        key=IronOSButton.SETTINGS_RESET,
        translation_key=IronOSButton.SETTINGS_RESET,
        press_fn=lambda api: api.write(CharSetting.SETTINGS_RESET, True),
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.CONFIG,
    ),
    IronOSButtonEntityDescription(
        key=IronOSButton.SETTINGS_SAVE,
        translation_key=IronOSButton.SETTINGS_SAVE,
        press_fn=lambda api: api.write(CharSetting.SETTINGS_SAVE, True),
        entity_category=EntityCategory.CONFIG,
    ),
    IronOSButtonEntityDescription(
        key=IronOSButton.BLE_ENABLED,
        translation_key=IronOSButton.BLE_ENABLED,
        press_fn=lambda api: api.write(CharSetting.BLE_ENABLED, False),
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.CONFIG,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IronOSConfigEntry,
    async_add_entities: AddEntitiesCallback,
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
        try:
            await self.entity_description.press_fn(self.coordinator.device)
        except CommunicationError as e:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="submit_setting_failed",
            ) from e
        await self.settings.async_request_refresh()
