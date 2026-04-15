"""Switch platform for the jvc_projector integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final

from jvcprojector import Command, command as cmd

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import JVCConfigEntry, JvcProjectorDataUpdateCoordinator
from .entity import JvcProjectorEntity


@dataclass(frozen=True, kw_only=True)
class JvcProjectorSwitchDescription(SwitchEntityDescription):
    """Describes JVC Projector switch entities."""

    command: type[Command]


SWITCHES: Final[tuple[JvcProjectorSwitchDescription, ...]] = (
    JvcProjectorSwitchDescription(
        key="low_latency_mode",
        command=cmd.LowLatencyMode,
        entity_registry_enabled_default=False,
    ),
    JvcProjectorSwitchDescription(
        key="eshift",
        command=cmd.EShift,
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: JVCConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the JVC Projector switch platform from a config entry."""
    coordinator = entry.runtime_data

    async_add_entities(
        JvcProjectorSwitchEntity(coordinator, description)
        for description in SWITCHES
        if coordinator.supports(description.command)
    )


class JvcProjectorSwitchEntity(JvcProjectorEntity, SwitchEntity):
    """JVC Projector class for switch entities."""

    def __init__(
        self,
        coordinator: JvcProjectorDataUpdateCoordinator,
        description: JvcProjectorSwitchDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator, description.command)
        self.command: type[Command] = description.command

        self.entity_description = description
        self._attr_translation_key = description.key
        self._attr_unique_id = f"{self._attr_unique_id}_{description.key}"

    @property
    def is_on(self) -> bool:
        """Return True if the entity is on."""
        return self.coordinator.data.get(self.command.name) == STATE_ON

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        await self.coordinator.device.set(self.command, STATE_ON)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await self.coordinator.device.set(self.command, STATE_OFF)
