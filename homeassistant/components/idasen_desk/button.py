"""Representation of Idasen Desk buttons."""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
import logging
from typing import Any, Final

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import IdasenDeskConfigEntry, IdasenDeskCoordinator
from .entity import IdasenDeskEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class IdasenDeskButtonDescription(ButtonEntityDescription):
    """Class to describe a IdasenDesk button entity."""

    press_action: Callable[
        [IdasenDeskCoordinator], Callable[[], Coroutine[Any, Any, Any]]
    ]


BUTTONS: Final = [
    IdasenDeskButtonDescription(
        key="connect",
        translation_key="connect",
        entity_category=EntityCategory.CONFIG,
        press_action=lambda coordinator: coordinator.async_connect,
    ),
    IdasenDeskButtonDescription(
        key="disconnect",
        translation_key="disconnect",
        entity_category=EntityCategory.CONFIG,
        press_action=lambda coordinator: coordinator.async_disconnect,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IdasenDeskConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set buttons for device."""
    coordinator = entry.runtime_data
    async_add_entities(IdasenDeskButton(coordinator, button) for button in BUTTONS)


class IdasenDeskButton(IdasenDeskEntity, ButtonEntity):
    """Defines a IdasenDesk button."""

    entity_description: IdasenDeskButtonDescription

    def __init__(
        self,
        coordinator: IdasenDeskCoordinator,
        description: IdasenDeskButtonDescription,
    ) -> None:
        """Initialize the IdasenDesk button entity."""
        super().__init__(f"{description.key}-{coordinator.address}", coordinator)
        self.entity_description = description

    async def async_press(self) -> None:
        """Triggers the IdasenDesk button press service."""
        _LOGGER.debug(
            "Trigger %s for %s",
            self.entity_description.key,
            self.coordinator.address,
        )
        await self.entity_description.press_action(self.coordinator)()

    @property
    def available(self) -> bool:
        """Connect/disconnect buttons should always be available."""
        return True
