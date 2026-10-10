"""Support for Meshtastic settings that are free text.

``device.tzdef`` is the node's POSIX timezone string.  It is one of the device
fields ``AdminModule::handleSetConfig`` applies live, so setting it does not
reboot the radio.
"""

from dataclasses import dataclass
from typing import override

from homeassistant.components.text import TextEntity, TextEntityDescription, TextMode
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MeshtasticConfigEntry
from .config_entity import (
    SECTION_DEVICE,
    MeshtasticConfigEntity,
    MeshtasticConfigSnapshot,
    async_get_config_snapshot,
)
from .coordinator import MeshtasticCoordinator

# Every write goes to the radio, which serves one admin message at a time.
PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class MeshtasticTextEntityDescription(TextEntityDescription):
    """Describes a Meshtastic gateway configuration text setting."""

    section: str
    field: str


TEXTS: tuple[MeshtasticTextEntityDescription, ...] = (
    MeshtasticTextEntityDescription(
        key="device_tzdef",
        translation_key="device_tzdef",
        section=SECTION_DEVICE,
        field="tzdef",
        mode=TextMode.TEXT,
        native_min=0,
        # The firmware stores a 65 byte buffer, one of which is the terminator.
        native_max=64,
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MeshtasticConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Meshtastic text entities from a config entry."""
    coordinator = entry.runtime_data.coordinator
    snapshot = await async_get_config_snapshot(entry)
    async_add_entities(
        MeshtasticConfigText(coordinator, snapshot, description)
        for description in TEXTS
    )


class MeshtasticConfigText(MeshtasticConfigEntity, TextEntity):
    """A textual gateway setting the firmware applies without rebooting."""

    entity_description: MeshtasticTextEntityDescription

    def __init__(
        self,
        coordinator: MeshtasticCoordinator,
        snapshot: MeshtasticConfigSnapshot,
        description: MeshtasticTextEntityDescription,
    ) -> None:
        """Initialise a gateway configuration text entity."""
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
    def native_value(self) -> str | None:
        """Return the text the node reported for this setting."""
        value = self.config_value
        return None if value is None else str(value)

    @override
    async def async_set_value(self, value: str) -> None:
        """Write the text and show it once the node acknowledged it."""
        await self.async_write_config(value)
        self.async_write_ha_state()
