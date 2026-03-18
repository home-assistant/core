"""Button entities for Bluesound."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from pyblu import Player

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,
    DeviceInfo,
    format_mac,
)
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import BluesoundCoordinator
from .media_player import DEFAULT_PORT
from .utils import format_unique_id

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


class BluesoundButton(CoordinatorEntity[BluesoundCoordinator], ButtonEntity):
    """Base class for Bluesound buttons."""

    _attr_has_entity_name = True
    entity_description: BluesoundButtonEntityDescription

    def __init__(
        self,
        coordinator: BluesoundCoordinator,
        player: Player,
        port: int,
        description: BluesoundButtonEntityDescription,
    ) -> None:
        """Initialize the Bluesound button."""
        super().__init__(coordinator)
        sync_status = coordinator.data.sync_status

        self.entity_description = description
        self._player = player
        self._attr_unique_id = (
            f"{description.key}-{format_unique_id(sync_status.mac, port)}"
        )

        if port == DEFAULT_PORT:
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, format_mac(sync_status.mac))},
                connections={(CONNECTION_NETWORK_MAC, format_mac(sync_status.mac))},
                name=sync_status.name,
                manufacturer=sync_status.brand,
                model=sync_status.model_name,
                model_id=sync_status.model,
            )
        else:
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, format_unique_id(sync_status.mac, port))},
                name=sync_status.name,
                manufacturer=sync_status.brand,
                model=sync_status.model_name,
                model_id=sync_status.model,
                via_device=(DOMAIN, format_mac(sync_status.mac)),
            )

    async def async_press(self) -> None:
        """Handle the button press."""
        await self.entity_description.press_fn(self._player)
