"""Support for Meshtastic settings that are selections.

``device.buzzer_mode`` is one of the device settings the firmware applies live:
it is not in the list that makes ``handleSetConfig`` keep ``requiresReboot``
true, so writing it neither reboots nor interrupts the mesh.
"""

from dataclasses import dataclass
from typing import override

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MeshtasticConfigEntry
from .config_entity import (
    BUZZER_MODES,
    SECTION_DEVICE,
    MeshtasticConfigEntity,
    MeshtasticConfigSnapshot,
    async_get_config_snapshot,
)
from .coordinator import MeshtasticCoordinator

# Every write goes to the radio, which serves one admin message at a time.
PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class MeshtasticSelectEntityDescription(SelectEntityDescription):
    """Describes a Meshtastic gateway configuration selection."""

    section: str
    field: str
    #: Enum member names, in protobuf number order.
    members: tuple[str, ...]


SELECTS: tuple[MeshtasticSelectEntityDescription, ...] = (
    MeshtasticSelectEntityDescription(
        key="device_buzzer_mode",
        translation_key="device_buzzer_mode",
        section=SECTION_DEVICE,
        field="buzzer_mode",
        members=BUZZER_MODES,
        options=list(BUZZER_MODES),
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MeshtasticConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Meshtastic selects from a config entry."""
    coordinator = entry.runtime_data.coordinator
    snapshot = await async_get_config_snapshot(entry)
    async_add_entities(
        MeshtasticConfigSelect(coordinator, snapshot, description)
        for description in SELECTS
    )


class MeshtasticConfigSelect(MeshtasticConfigEntity, SelectEntity):
    """An enumerated gateway setting the firmware applies without rebooting."""

    entity_description: MeshtasticSelectEntityDescription

    def __init__(
        self,
        coordinator: MeshtasticCoordinator,
        snapshot: MeshtasticConfigSnapshot,
        description: MeshtasticSelectEntityDescription,
    ) -> None:
        """Initialise a gateway configuration select."""
        super().__init__(
            coordinator,
            snapshot,
            key=description.key,
            section=description.section,
            field=description.field,
        )
        self.entity_description = description

    @property
    @override
    def current_option(self) -> str | None:
        """Return the enum member the node reported, by name."""
        value = self.config_value
        members = self.entity_description.members
        if not isinstance(value, int) or not 0 <= value < len(members):
            return None
        return members[value]

    @override
    async def async_select_option(self, option: str) -> None:
        """Write the selected member and show it once the node acked it."""
        await self.async_write_config(self.entity_description.members.index(option))
        self.async_write_ha_state()
