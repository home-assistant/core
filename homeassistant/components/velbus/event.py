"""Support for Velbus Event entities."""

from typing import override

from velbusaio.channels import (
    Button as VelbusaioButton,
    ButtonCounter as VelbusaioButtonCounter,
)

from homeassistant.components.event import EventDeviceClass, EventEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import VelbusConfigEntry
from .entity import VelbusEntity

EVENT_SHORT_PRESS = "short_press"
EVENT_LONG_PRESS = "long_press"
EVENT_TYPES = [EVENT_SHORT_PRESS, EVENT_LONG_PRESS]

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VelbusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Velbus event entities based on config entry."""
    await entry.runtime_data.scan_task
    async_add_entities(
        VelbusButtonEvent(channel)
        for channel in entry.runtime_data.controller.get_all_button()
    )


class VelbusButtonEvent(VelbusEntity, EventEntity):
    """Representation of a Velbus button event entity."""

    _channel: VelbusaioButton | VelbusaioButtonCounter
    _attr_device_class = EventDeviceClass.BUTTON
    _attr_event_types = EVENT_TYPES

    def __init__(self, channel: VelbusaioButton | VelbusaioButtonCounter) -> None:
        """Initialize a Velbus button event entity."""
        super().__init__(channel)
        self._was_closed = self._channel.is_closed()
        self._long_seen = self._was_closed and self._is_long_pressed()

    def _is_long_pressed(self) -> bool:
        """Return if Velbus has reported a long press."""
        return bool(self._channel.get_channel_info().get("long", False))

    @override
    async def _on_update(self) -> None:
        """Handle status updates from the channel."""
        closed = self._channel.is_closed()
        long_pressed = self._is_long_pressed()

        if not self._was_closed and closed:
            self._long_seen = long_pressed
        elif closed and long_pressed:
            self._long_seen = True
        elif self._was_closed and not closed:
            self._trigger_event(
                EVENT_LONG_PRESS if self._long_seen else EVENT_SHORT_PRESS
            )
            self._long_seen = False
        elif not closed:
            self._long_seen = False

        self._was_closed = closed
        await super()._on_update()
