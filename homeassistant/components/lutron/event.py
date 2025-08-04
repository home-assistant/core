"""Support for Lutron events."""

from enum import StrEnum

from homeassistant.components.event import EventEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import slugify

from . import ATTR_ACTION, ATTR_FULL_ID, ATTR_UUID, DOMAIN, LutronData
from .aiolip import Button, LutronController
from .entity import LutronKeypadComponent


class LutronEventType(StrEnum):
    """Lutron event types."""

    PRESS = "press"
    RELEASE = "release"
    HOLD = "hold"
    DOUBLE_TAP = "double_tap"
    HOLD_RELEASE = "hold_release"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Lutron event platform."""
    entry_data: LutronData = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        LutronEventEntity(button, entry_data.controller)
        for button in entry_data.buttons
    )


class LutronEventEntity(LutronKeypadComponent, EventEntity):
    """Representation of a button on a Lutron keypad.

    This is responsible for firing events as keypad buttons are press
    (and possibly release, depending on the button type). It is not
    represented as an entity; it simply fires events.
    """

    _lutron_device: Button
    _attr_translation_key = "button"
    action_number_to_event = {
        3: LutronEventType.PRESS,
        4: LutronEventType.RELEASE,
        5: LutronEventType.HOLD,
        6: LutronEventType.DOUBLE_TAP,
        32: LutronEventType.HOLD_RELEASE,
    }

    def __init__(
        self,
        button: Button,
        controller: LutronController,
    ) -> None:
        """Initialize the button."""
        super().__init__(button, controller)
        self._attr_name = self.name
        self._has_release_event = (
            button.button_type is not None
            and button.button_type in ("RaiseLower", "DualAction")
        )
        self._attr_event_types = [
            LutronEventType.PRESS,
            LutronEventType.RELEASE,
            LutronEventType.HOLD,
            LutronEventType.HOLD_RELEASE,
            LutronEventType.DOUBLE_TAP,
        ]

        self._full_id = slugify(f"{self.device_name}: {self.name}")
        self._id = slugify(f"{self.keypad_name}: {self.name}")  # e.g. keypad_12_btn_3

    def _update_callback(self, value: int):
        """Trigger an event.

        value is the action_number of the button that was pressed.
        """
        event = self.action_number_to_event[value]
        if event:
            data = {
                ATTR_ID: self._id,
                ATTR_ACTION: event,
                ATTR_FULL_ID: self._full_id,
                ATTR_UUID: self._lutron_device.uuid,
            }
            self.hass.bus.fire("lutron_event", data)
            self._trigger_event(event)
            self.schedule_update_ha_state()
