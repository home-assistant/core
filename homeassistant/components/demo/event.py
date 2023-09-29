"""Demo platform that offers a fake event entity."""
from __future__ import annotations

from homeassistant.components.event import EventDeviceClass, EventEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the demo event platform."""
    async_add_entities([DemoEvent()])


class DemoEvent(EventEntity):
    """Representation of a demo event entity."""

    _attr_device_class = EventDeviceClass.BUTTON
    _attr_event_types = ["pressed"]
    _attr_has_entity_name = True
    _attr_name = "Button press"
    _attr_should_poll = False
    _attr_translation_key = "push"
    _attr_unique_id = "push"

    def __init__(self) -> None:
        """Initialize the Demo event entity."""
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, "push")},
        )

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self.hass.bus.async_listen("demo_button_pressed", self._async_handle_event)

    @callback
    def _async_handle_event(self, _: Event) -> None:
        """Handle the demo button event."""
        self._trigger_event("pressed")
        self.async_write_ha_state()
