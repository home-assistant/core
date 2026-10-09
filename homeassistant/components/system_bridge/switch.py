"""Support for System Bridge switches."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, override

from systembridgeconnector.models.discord_control import DiscordAction
from systembridgeconnector.models.modules import Discord

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import SystemBridgeConfigEntry, SystemBridgeDataUpdateCoordinator
from .entity import SystemBridgeEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class SystemBridgeDiscordSwitchEntityDescription(SwitchEntityDescription):
    """Class describing System Bridge Discord switch entities."""

    value_fn: Callable[[Discord], bool | None]
    on_action: DiscordAction
    off_action: DiscordAction


DISCORD_SWITCH_TYPES: tuple[SystemBridgeDiscordSwitchEntityDescription, ...] = (
    SystemBridgeDiscordSwitchEntityDescription(
        key="discord_mute",
        translation_key="discord_mute",
        value_fn=lambda discord: discord.mute,
        on_action=DiscordAction.MUTE,
        off_action=DiscordAction.UNMUTE,
    ),
    SystemBridgeDiscordSwitchEntityDescription(
        key="discord_deafen",
        translation_key="discord_deafen",
        value_fn=lambda discord: discord.deaf,
        on_action=DiscordAction.DEAFEN,
        off_action=DiscordAction.UNDEAFEN,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SystemBridgeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up System Bridge switches based on a config entry."""
    coordinator = entry.runtime_data

    if coordinator.data.discord is None:
        return

    async_add_entities(
        SystemBridgeDiscordSwitch(coordinator, description, entry.data[CONF_PORT])
        for description in DISCORD_SWITCH_TYPES
    )


class SystemBridgeDiscordSwitch(SystemBridgeEntity, SwitchEntity):
    """Define a System Bridge Discord switch."""

    entity_description: SystemBridgeDiscordSwitchEntityDescription

    def __init__(
        self,
        coordinator: SystemBridgeDataUpdateCoordinator,
        description: SystemBridgeDiscordSwitchEntityDescription,
        api_port: int,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, api_port, description.key)
        self.entity_description = description

    @property
    @override
    def available(self) -> bool:
        """Return True if entity is available."""
        discord = self.coordinator.data.discord
        return (
            super().available
            and discord is not None
            and discord.connected
            and discord.authenticated
        )

    @property
    @override
    def is_on(self) -> bool | None:
        """Return the state of the switch."""
        assert self.coordinator.data.discord is not None
        return self.entity_description.value_fn(self.coordinator.data.discord)

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self.coordinator.async_discord_control(self.entity_description.on_action)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self.coordinator.async_discord_control(self.entity_description.off_action)
