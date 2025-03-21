"""Support for select entities through the SmartThings cloud API."""

from __future__ import annotations

from dataclasses import dataclass

from pysmartthings import Attribute, Capability, Command, SmartThings

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import FullDevice, SmartThingsConfigEntry
from .const import MAIN
from .entity import SmartThingsEntity


@dataclass(frozen=True, kw_only=True)
class SmartThingsSelectEntityDescription(SelectEntityDescription):
    """Class describing SmartThings select entities."""

    key: Capability
    options_attribute: Attribute
    state_attribute: Attribute
    command: Command


CAPABILITIES_TO_SELECT: dict[Capability, SmartThingsSelectEntityDescription] = {
    Capability.CUSTOM_WASHER_RINSE_CYCLES: SmartThingsSelectEntityDescription(
        key=Capability.CUSTOM_WASHER_RINSE_CYCLES,
        translation_key="washer_rinse_cycles",
        options_attribute=Attribute.SUPPORTED_WASHER_RINSE_CYCLES,
        state_attribute=Attribute.WASHER_RINSE_CYCLES,
        command=Command.SET_WASHER_RINSE_CYCLES,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SmartThingsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add select entities for a config entry."""
    entry_data = entry.runtime_data
    async_add_entities(
        SmartThingsSelect(
            entry_data.client, device, entity_description, entry_data.rooms
        )
        for device in entry_data.devices.values()
        for entity_description in CAPABILITIES_TO_SELECT.values()
        if entity_description.key in device.status[MAIN]
    )


class SmartThingsSelect(SmartThingsEntity, SelectEntity):
    """Define a SmartThings select."""

    entity_description: SmartThingsSelectEntityDescription

    def __init__(
        self,
        client: SmartThings,
        device: FullDevice,
        entity_description: SmartThingsSelectEntityDescription,
        rooms: dict[str, str],
    ) -> None:
        """Initialize the instance."""
        super().__init__(client, device, rooms, {entity_description.key})
        self.entity_description = entity_description
        self._attr_unique_id = f"{device.device.device_id}.{entity_description.key}"

    @property
    def current_option(self) -> str | None:
        """Return the current option."""
        return self.get_attribute_value(
            self.entity_description.key, self.entity_description.state_attribute
        )

    @property
    def options(self) -> list[str]:
        """Return the list of options."""
        return self.get_attribute_value(
            self.entity_description.key, self.entity_description.options_attribute
        )

    async def async_select_option(self, option: str) -> None:
        """Select an option."""
        await self.execute_device_command(
            self.entity_description.key,
            self.entity_description.command,
            argument=option,
        )
