"""Support for events through the SmartThings cloud API."""

from __future__ import annotations

from typing import cast

from pysmartthings import Attribute, Capability, Component, DeviceEvent, SmartThings

from homeassistant.components.event import EventDeviceClass, EventEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import FullDevice, SmartThingsConfigEntry
from .entity import SmartThingsEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SmartThingsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add events for a config entry."""
    entry_data = entry.runtime_data
    async_add_entities(
        SmartThingsButtonEvent(entry_data.client, entry_data.rooms, device, component)
        for device in entry_data.devices.values()
        for component in device.device.components
        if Capability.BUTTON in component.capabilities
    )


class SmartThingsButtonEvent(SmartThingsEntity, EventEntity):
    """Define a SmartThings event."""

    _attr_device_class = EventDeviceClass.BUTTON
    _attr_translation_key = "button"

    def __init__(
        self,
        client: SmartThings,
        rooms: dict[str, str],
        device: FullDevice,
        component: Component,
    ) -> None:
        """Init the class."""
        super().__init__(
            client, device, rooms, {Capability.BUTTON}, component=component.id
        )
        self._attr_name = component.label
        self._attr_unique_id = (
            f"{device.device.device_id}_{component.id}_{Capability.BUTTON}"
        )

    @property
    def event_types(self) -> list[str]:
        """Return the event types."""
        return self.get_attribute_value(
            Capability.BUTTON, Attribute.SUPPORTED_BUTTON_VALUES
        )

    def _update_handler(self, event: DeviceEvent) -> None:
        self._trigger_event(cast(str, event.value))
        self.async_write_ha_state()
