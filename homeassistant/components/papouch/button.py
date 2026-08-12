"""Button platform for the Papouch integration."""

from typing import Any, override

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PapouchConfigEntry
from .coordinator import PapouchDataUpdateCoordinator
from .entity import PapouchEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PapouchConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the button platform."""
    coordinator = entry.runtime_data
    device = coordinator.device

    entities = [
        PapouchCommandButton(coordinator, entry, btn_data)
        for btn_data in device.get_supported_buttons()
    ]

    async_add_entities(entities)


class PapouchCommandButton(PapouchEntity, ButtonEntity):
    """Representation of a generic Papouch button entity."""

    def __init__(
        self,
        coordinator: PapouchDataUpdateCoordinator,
        entry: PapouchConfigEntry,
        btn_data: dict[str, Any],
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator, entry)

        mac = format_mac(coordinator.device.mac_address)

        self.cmd_type = btn_data["cmd"]

        self._attr_unique_id = f"{mac}_btn_{self.cmd_type}"
        self._attr_name = btn_data["name"]

        if "icon" in btn_data:
            self._attr_icon = btn_data["icon"]

    @override
    async def async_press(self) -> None:
        """Execute the command."""
        await self.coordinator.device.execute_button_command(self.cmd_type)
        self.coordinator.async_set_updated_data(self.coordinator.data)
