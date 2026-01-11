"""Select platform for the jvc_projector integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from jvcprojector import Command, command as cmd

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import JVCConfigEntry, JvcProjectorDataUpdateCoordinator
from .entity import JvcProjectorEntity


@dataclass(frozen=True, kw_only=True)
class JvcProjectorSelectDescription(SelectEntityDescription):
    """Describes JVC Projector select entities."""

    command: type[Command]


SELECTS: Final[tuple[JvcProjectorSelectDescription, ...]] = (
    JvcProjectorSelectDescription(key="input", command=cmd.Input),
    JvcProjectorSelectDescription(
        key="installation_mode",
        command=cmd.InstallationMode,
        entity_registry_enabled_default=False,
    ),
    JvcProjectorSelectDescription(
        key="light_power",
        command=cmd.LightPower,
        entity_registry_enabled_default=False,
    ),
    JvcProjectorSelectDescription(
        key="dynamic_control",
        command=cmd.DynamicControl,
        entity_registry_enabled_default=False,
    ),
    JvcProjectorSelectDescription(
        key="low_latency_mode",
        command=cmd.LowLatencyMode,
        entity_registry_enabled_default=False,
    ),
    JvcProjectorSelectDescription(
        key="clear_motion_drive",
        command=cmd.ClearMotionDrive,
        entity_registry_enabled_default=False,
    ),
    JvcProjectorSelectDescription(
        key="anamorphic",
        command=cmd.Anamorphic,
        entity_registry_enabled_default=False,
    ),
    JvcProjectorSelectDescription(
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
    """Set up the JVC Projector platform from a config entry."""
    coordinator = entry.runtime_data

    async_add_entities(
        JvcProjectorSelectEntity(coordinator, description)
        for description in SELECTS
        if coordinator.supports(description.command)
    )


class JvcProjectorSelectEntity(JvcProjectorEntity, SelectEntity):
    """Representation of a JVC Projector select entity."""

    def __init__(
        self,
        coordinator: JvcProjectorDataUpdateCoordinator,
        description: JvcProjectorSelectDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)

        self.entity_description = description
        self.command: type[Command] = description.command

        self._attr_translation_key = description.key
        self._attr_unique_id = f"{self._attr_unique_id}_{description.key}"
        self._attr_options = coordinator.get_options(self.command.name)

    @property
    def current_option(self) -> str | None:
        """Return the selected entity option to represent the entity state."""
        return self.coordinator.data.get(self.command.name)

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        await self.coordinator.device.set(self.command, option)

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        await super().async_added_to_hass()
        self.coordinator.register(self.command)

    async def async_will_remove_from_hass(self) -> None:
        """Unregister callbacks."""
        self.coordinator.unregister(self.command)
        await super().async_will_remove_from_hass()
