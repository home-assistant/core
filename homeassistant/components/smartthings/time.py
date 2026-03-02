"""Time platform for SmartThings."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import time

from pysmartthings import Attribute, Capability, Command, SmartThings

from homeassistant.components.time import TimeEntity, TimeEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import FullDevice, SmartThingsConfigEntry
from .const import MAIN
from .entity import SmartThingsEntity


@dataclass(frozen=True, kw_only=True)
class SmartThingsTimeEntityDescription(TimeEntityDescription):
    """Describe a SmartThings time entity."""

    attribute: Attribute


DND_ENTITIES = [
    SmartThingsTimeEntityDescription(
        key=Attribute.START_TIME,
        translation_key="do_not_disturb_start_time",
        attribute=Attribute.START_TIME,
        entity_category=EntityCategory.CONFIG,
    ),
    SmartThingsTimeEntityDescription(
        key=Attribute.END_TIME,
        translation_key="do_not_disturb_end_time",
        attribute=Attribute.END_TIME,
        entity_category=EntityCategory.CONFIG,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SmartThingsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add time entities for a config entry."""
    entry_data = entry.runtime_data
    async_add_entities(
        SmartThingsDnDTime(entry_data.client, device, description)
        for device in entry_data.devices.values()
        if Capability.CUSTOM_DO_NOT_DISTURB_MODE in device.status.get(MAIN, {})
        for description in DND_ENTITIES
    )


class SmartThingsDnDTime(SmartThingsEntity, TimeEntity):
    """Define a SmartThings time entity."""

    entity_description: SmartThingsTimeEntityDescription

    def __init__(
        self,
        client: SmartThings,
        device: FullDevice,
        entity_description: SmartThingsTimeEntityDescription,
    ) -> None:
        """Initialize the time entity."""
        super().__init__(client, device, {Capability.CUSTOM_DO_NOT_DISTURB_MODE})
        self.entity_description = entity_description
        self._attr_unique_id = f"{device.device.device_id}_{MAIN}_{Capability.CUSTOM_DO_NOT_DISTURB_MODE}_{entity_description.attribute}_{entity_description.attribute}"

    async def async_set_value(self, value: time) -> None:
        """Set the time value."""
        payload = {
            "mode": self.get_attribute_value(
                Capability.CUSTOM_DO_NOT_DISTURB_MODE, Attribute.DO_NOT_DISTURB
            ),
            "startTime": self.get_attribute_value(
                Capability.CUSTOM_DO_NOT_DISTURB_MODE, Attribute.START_TIME
            ),
            "endTime": self.get_attribute_value(
                Capability.CUSTOM_DO_NOT_DISTURB_MODE, Attribute.END_TIME
            ),
        }
        await self.execute_device_command(
            Capability.CUSTOM_DO_NOT_DISTURB_MODE,
            Command.SET_DO_NOT_DISTURB_MODE,
            {
                **payload,
                self.entity_description.attribute: f"{value.hour:02d}{value.minute:02d}",
            },
        )

    @property
    def native_value(self) -> time:
        """Return the time value."""
        state = self.get_attribute_value(
            Capability.CUSTOM_DO_NOT_DISTURB_MODE, self.entity_description.attribute
        )
        return time(int(state[:2]), int(state[3:5]))
