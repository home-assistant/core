"""Support for button entities."""

from typing import override

from togrill_bluetooth.packets import PacketA5Write

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import ToGrillConfigEntry
from .coordinator import ToGrillCoordinator
from .entity import ToGrillEntity

PARALLEL_UPDATES = 0

ENTITY_DESCRIPTIONS = (
    ButtonEntityDescription(
        key="silence",
        translation_key="silence",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ToGrillConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up button based on a config entry."""

    coordinator = entry.runtime_data

    async_add_entities(
        ToGrillButton(coordinator, entity_description)
        for entity_description in ENTITY_DESCRIPTIONS
    )


class ToGrillButton(ToGrillEntity, ButtonEntity):
    """Representation of a button."""

    def __init__(
        self,
        coordinator: ToGrillCoordinator,
        entity_description: ButtonEntityDescription,
    ) -> None:
        """Initialize."""

        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = f"{coordinator.address}_{entity_description.key}"

    @override
    async def async_press(self) -> None:
        """Silence any active alarm on the device."""
        await self._write_packet(PacketA5Write())
