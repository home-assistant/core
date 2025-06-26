"""Support for button entities through the SmartThings cloud API."""

from __future__ import annotations

from dataclasses import dataclass

from pysmartthings import Capability, Command, SmartThings

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import FullDevice, SmartThingsConfigEntry
from .const import MAIN
from .entity import SmartThingsEntity


@dataclass(frozen=True, kw_only=True)
class SmartThingsButtonDescription(ButtonEntityDescription):
    """Class describing SmartThings button entities."""

    key: Capability
    command: Command


CAPABILITIES_TO_BUTTONS: dict[Capability | str, SmartThingsButtonDescription] = {
    Capability.OVEN_OPERATING_STATE: SmartThingsButtonDescription(
        key=Capability.OVEN_OPERATING_STATE,
        translation_key="stop",
        command=Command.STOP,
    ),
    Capability.CUSTOM_WATER_FILTER: SmartThingsButtonDescription(
        key=Capability.CUSTOM_WATER_FILTER,
        translation_key="reset_water_filter",
        command=Command.RESET_WATER_FILTER,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SmartThingsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add button entities for a config entry."""
    entry_data = entry.runtime_data
    async_add_entities(
        SmartThingsButtonEntity(
            entry_data.client, device, CAPABILITIES_TO_BUTTONS[capability]
        )
        for device in entry_data.devices.values()
        for capability in device.status[MAIN]
        if capability in CAPABILITIES_TO_BUTTONS
    )


class SmartThingsButtonEntity(SmartThingsEntity, ButtonEntity):
    """Define a SmartThings button."""

    entity_description: SmartThingsButtonDescription

    def __init__(
        self,
        client: SmartThings,
        device: FullDevice,
        entity_description: SmartThingsButtonDescription,
    ) -> None:
        """Initialize the instance."""
        super().__init__(client, device, set())
        self.entity_description = entity_description
        self._attr_unique_id = f"{device.device.device_id}_{MAIN}_{entity_description.key}_{entity_description.command}"

    async def async_press(self) -> None:
        """Press the button."""
        await self.execute_device_command(
            self.entity_description.key,
            self.entity_description.command,
        )
