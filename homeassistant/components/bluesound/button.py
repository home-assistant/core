"""Button entities for Bluesound."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, override

from pyblu import Player

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import BluesoundCoordinator
from .entity import BluesoundEntity

if TYPE_CHECKING:
    from . import BluesoundConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BluesoundConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Bluesound entry."""

    async_add_entities(
        BluesoundButton(
            config_entry.runtime_data.coordinator,
            config_entry.runtime_data.player,
            config_entry.data[CONF_PORT],
            description,
        )
        for description in BUTTON_DESCRIPTIONS
    )


@dataclass(kw_only=True, frozen=True)
class BluesoundButtonEntityDescription(ButtonEntityDescription):
    """Description for Bluesound button entities."""

    press_fn: Callable[[Player], Awaitable[None]]


async def clear_sleep_timer(player: Player) -> None:
    """Clear the sleep timer."""
    sleep = -1
    while sleep != 0:
        sleep = await player.sleep_timer()


async def set_sleep_timer(player: Player) -> None:
    """Set the sleep timer."""
    await player.sleep_timer()


BUTTON_DESCRIPTIONS = [
    BluesoundButtonEntityDescription(
        key="set_sleep_timer",
        translation_key="set_sleep_timer",
        entity_registry_enabled_default=False,
        press_fn=set_sleep_timer,
    ),
    BluesoundButtonEntityDescription(
        key="clear_sleep_timer",
        translation_key="clear_sleep_timer",
        entity_registry_enabled_default=False,
        press_fn=clear_sleep_timer,
    ),
]


class BluesoundButton(BluesoundEntity, ButtonEntity):
    """Base class for Bluesound buttons."""

    entity_description: BluesoundButtonEntityDescription

    def __init__(
        self,
        coordinator: BluesoundCoordinator,
        player: Player,
        port: int,
        description: BluesoundButtonEntityDescription,
    ) -> None:
        """Initialize the Bluesound button."""
        super().__init__(
            coordinator,
            player,
            port=port,
            sync_status=coordinator.data.sync_status,
            unique_id_prefix=description.key,
        )

        self.entity_description = description

    @override
    async def async_press(self) -> None:
        """Handle the button press."""
        await self.entity_description.press_fn(self._player)
