"""Support for System Bridge numbers."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from systembridgeconnector.models.discord_control import DiscordAction
from systembridgeconnector.models.modules import Discord

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.const import CONF_PORT, PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import SystemBridgeConfigEntry, SystemBridgeDataUpdateCoordinator
from .entity import SystemBridgeEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class SystemBridgeDiscordNumberEntityDescription(NumberEntityDescription):
    """Class describing System Bridge Discord number entities."""

    value_fn: Callable[[Discord], float | None]
    action: DiscordAction


DISCORD_NUMBER_TYPES: tuple[SystemBridgeDiscordNumberEntityDescription, ...] = (
    SystemBridgeDiscordNumberEntityDescription(
        key="discord_input_volume",
        translation_key="discord_input_volume",
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda discord: discord.input_volume,
        action=DiscordAction.SET_INPUT_VOLUME,
    ),
    SystemBridgeDiscordNumberEntityDescription(
        key="discord_output_volume",
        translation_key="discord_output_volume",
        native_min_value=0,
        native_max_value=200,
        native_step=1,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda discord: discord.output_volume,
        action=DiscordAction.SET_OUTPUT_VOLUME,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SystemBridgeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up System Bridge numbers based on a config entry."""
    coordinator = entry.runtime_data

    if coordinator.data.discord is None:
        return

    async_add_entities(
        SystemBridgeDiscordNumber(coordinator, description, entry.data[CONF_PORT])
        for description in DISCORD_NUMBER_TYPES
    )


class SystemBridgeDiscordNumber(SystemBridgeEntity, NumberEntity):
    """Define a System Bridge Discord number."""

    entity_description: SystemBridgeDiscordNumberEntityDescription

    def __init__(
        self,
        coordinator: SystemBridgeDataUpdateCoordinator,
        description: SystemBridgeDiscordNumberEntityDescription,
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
    def native_value(self) -> float | None:
        """Return the current volume."""
        assert self.coordinator.data.discord is not None
        return self.entity_description.value_fn(self.coordinator.data.discord)

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Set the volume."""
        await self.coordinator.async_discord_control(
            self.entity_description.action, value
        )
