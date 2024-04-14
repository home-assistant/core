"""Buttons for the SimpliSafe integration."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from simplipy.errors import SimplipyError
from simplipy.system import System

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SimpliSafe, SimpliSafeEntity
from .const import DOMAIN
from .typing import SystemType


@dataclass(frozen=True, kw_only=True)
class SimpliSafeButtonDescription(ButtonEntityDescription):
    """Describe a SimpliSafe button entity."""

    push_action: Callable[[System], Awaitable]


BUTTON_KIND_CLEAR_NOTIFICATIONS = "clear_notifications"


async def _async_clear_notifications(system: System) -> None:
    """Reboot the SimpliSafe."""
    await system.async_clear_notifications()


BUTTON_DESCRIPTIONS = (
    SimpliSafeButtonDescription(
        key=BUTTON_KIND_CLEAR_NOTIFICATIONS,
        translation_key=BUTTON_KIND_CLEAR_NOTIFICATIONS,
        push_action=_async_clear_notifications,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up SimpliSafe buttons based on a config entry."""
    simplisafe = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            SimpliSafeButton(simplisafe, system, description)
            for system in simplisafe.systems.values()
            for description in BUTTON_DESCRIPTIONS
        ]
    )


class SimpliSafeButton(SimpliSafeEntity, ButtonEntity):
    """Define a SimpliSafe button."""

    _attr_entity_category = EntityCategory.CONFIG

    entity_description: SimpliSafeButtonDescription

    def __init__(
        self,
        simplisafe: SimpliSafe,
        system: SystemType,
        description: SimpliSafeButtonDescription,
    ) -> None:
        """Initialize the SimpliSafe alarm."""
        super().__init__(simplisafe, system)

        self.entity_description = description

    async def async_press(self) -> None:
        """Send out a restart command."""
        try:
            await self.entity_description.push_action(self._system)
        except SimplipyError as err:
            raise HomeAssistantError(
                f'Error while pressing button "{self.entity_id}": {err}'
            ) from err
