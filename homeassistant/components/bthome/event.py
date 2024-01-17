"""Support for bthome event entities."""
from __future__ import annotations

from homeassistant.components.event import (
    EventDeviceClass,
    EventEntity,
    EventEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import format_discovered_event_class_name, format_event_dispatcher_name
from .const import (
    DOMAIN,
    EVENT_CLASS_BUTTON,
    EVENT_CLASS_DIMMER,
    EVENT_PROPERTIES,
    EVENT_TYPE,
    BTHomeBleEvent,
)
from .coordinator import BTHomePassiveBluetoothProcessorCoordinator

DESCRIPTIONS_BY_EVENT_CLASS = {
    EVENT_CLASS_BUTTON: EventEntityDescription(
        key=EVENT_CLASS_BUTTON,
        name="Button",
        event_types=[
            "press",
            "double_press",
            "triple_press",
            "long_press",
            "long_double_press",
            "long_triple_press",
        ],
        device_class=EventDeviceClass.BUTTON,
    ),
    EVENT_CLASS_DIMMER: EventEntityDescription(
        key=EVENT_CLASS_DIMMER,
        name="Dimmer",
        event_types=["rotate_left", "rotate_right"],
    ),
}


class BTHomeEventEntity(EventEntity):
    """Representation of a BTHome event entity."""

    _attr_should_poll = False

    def __init__(self, address: str, event_class: str) -> None:
        """Initialise a BTHome event entity."""
        self.address = address
        self.event_class = event_class
        self.entity_description = DESCRIPTIONS_BY_EVENT_CLASS[event_class]

    async def async_added_to_hass(self) -> None:
        """Entity added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                format_event_dispatcher_name(self.address, self.event_class),
                self._handle_event,
            )
        )

    @callback
    def _handle_event(self, event: BTHomeBleEvent) -> None:
        self._trigger_event(event[EVENT_TYPE], event[EVENT_PROPERTIES])
        self.async_write_ha_state()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up BTHome event."""
    coordinator: BTHomePassiveBluetoothProcessorCoordinator = hass.data[DOMAIN][
        entry.entry_id
    ]
    address = coordinator.address
    async_add_entities(
        BTHomeEventEntity(address, event_class)
        for event_class in coordinator.discovered_event_classes
    )

    def _async_discovered_event_class(event_class: str) -> None:
        """Handle a discovered event class."""
        async_add_entities([BTHomeEventEntity(address, event_class)])

    entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            format_discovered_event_class_name(address),
            _async_discovered_event_class,
        )
    )
