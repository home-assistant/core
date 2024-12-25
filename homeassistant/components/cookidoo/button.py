"""Support for Cookidoo buttons."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from cookidoo_api import Cookidoo, CookidooException

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import CookidooConfigEntry, CookidooDataUpdateCoordinator
from .entity import CookidooBaseEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class CookidooButtonEntityDescription(ButtonEntityDescription):
    """Describes cookidoo button entity."""

    press_fn: Callable[[Cookidoo], Awaitable[None]]


TODO_CLEAR = CookidooButtonEntityDescription(
    key="todo_clear",
    translation_key="todo_clear",
    press_fn=lambda client: client.clear_shopping_list(),
    entity_registry_enabled_default=False,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CookidooConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Cookidoo button entities based on a config entry."""
    coordinator = entry.runtime_data

    async_add_entities([CookidooButton(coordinator, TODO_CLEAR)])


class CookidooButton(CookidooBaseEntity, ButtonEntity):
    """Defines an Cookidoo button."""

    entity_description: CookidooButtonEntityDescription

    def __init__(
        self,
        coordinator: CookidooDataUpdateCoordinator,
        description: CookidooButtonEntityDescription,
    ) -> None:
        """Initialize cookidoo button."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{description.key}"

    async def async_press(self) -> None:
        """Press the button."""
        try:
            await self.entity_description.press_fn(self.coordinator.cookidoo)
        except CookidooException as e:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="button_clear_todo_failed",
            ) from e
        await self.coordinator.async_refresh()
