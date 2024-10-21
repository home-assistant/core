"""Creates button entities for the Husqvarna Automower integration."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import logging
from typing import Any

from aioautomower.model import MowerAttributes
from aioautomower.session import AutomowerSession

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AutomowerConfigEntry
from .coordinator import AutomowerDataUpdateCoordinator
from .entity import (
    AutomowerAvailableEntity,
    _check_error_free,
    handle_sending_exception,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class AutomowerButtonEntityDescription(ButtonEntityDescription):
    """Describes Automower button entities."""

    available_fn: Callable[[MowerAttributes], bool] = lambda _: True
    exists_fn: Callable[[MowerAttributes], bool] = lambda _: True
    press_fn: Callable[[AutomowerSession, str], Awaitable[Any]]


MOWER_BUTTON_TYPES: tuple[AutomowerButtonEntityDescription, ...] = (
    AutomowerButtonEntityDescription(
        key="confirm_error",
        translation_key="confirm_error",
        available_fn=lambda data: data.mower.is_error_confirmable,
        exists_fn=lambda data: data.capabilities.can_confirm_error,
        press_fn=lambda session, mower_id: session.commands.error_confirm(mower_id),
    ),
    AutomowerButtonEntityDescription(
        key="sync_clock",
        translation_key="sync_clock",
        available_fn=_check_error_free,
        press_fn=lambda session, mower_id: session.commands.set_datetime(mower_id),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AutomowerConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up button platform."""
    coordinator = entry.runtime_data
    async_add_entities(
        AutomowerButtonEntity(mower_id, coordinator, description)
        for mower_id in coordinator.data
        for description in MOWER_BUTTON_TYPES
        if description.exists_fn(coordinator.data[mower_id])
    )


class AutomowerButtonEntity(AutomowerAvailableEntity, ButtonEntity):
    """Defining the AutomowerButtonEntity."""

    entity_description: AutomowerButtonEntityDescription

    def __init__(
        self,
        mower_id: str,
        coordinator: AutomowerDataUpdateCoordinator,
        description: AutomowerButtonEntityDescription,
    ) -> None:
        """Set up AutomowerButtonEntity."""
        super().__init__(mower_id, coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{mower_id}_{description.key}"

    @property
    def available(self) -> bool:
        """Return the available attribute of the entity."""
        return self.entity_description.available_fn(self.mower_attributes)

    @handle_sending_exception()
    async def async_press(self) -> None:
        """Send a command to the mower."""
        await self.entity_description.press_fn(self.coordinator.api, self.mower_id)
