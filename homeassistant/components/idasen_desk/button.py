"""Representation of Idasen Desk buttons."""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
import logging
from typing import Any, Final

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DeskData, IdasenDeskCoordinator
from .const import DOMAIN
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
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set buttons for device."""
    data: DeskData = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(IdasenDeskButton(data, button) for button in BUTTONS)


class IdasenDeskButton(IdasenDeskEntity, ButtonEntity):
    """Defines a IdasenDesk button."""

    entity_description: IdasenDeskButtonDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        desk_data: DeskData,
        description: IdasenDeskButtonDescription,
    ) -> None:
        """Initialize the IdasenDesk button entity."""
        super().__init__(f"{description.key}-{desk_data.address}", desk_data)
        self.entity_description = description
        self._address = desk_data.address
        self._coordinator = desk_data.coordinator

    async def async_press(self) -> None:
        """Triggers the IdasenDesk button press service."""
        _LOGGER.debug(
            "Trigger %s for %s",
            self.entity_description.key,
            self._address,
        )
        await self.entity_description.press_action(self._coordinator)()

    @property
    def available(self) -> bool:
        """Connect/disconnect buttons should always be available."""
        return True
