"""Event platform for Easywave transmitters (type-1 individual button mode).

Each physical button on a transmitter is represented as a dedicated EventEntity.
Using EventEntity instead of SensorEntity is the correct HA pattern: it fires a
timestamped event on every button interaction, generates no platform device
triggers (event/ has no device_trigger.py), and pairs cleanly with the
integration's own device triggers in device_trigger.py.
"""

from homeassistant.components.event import EventDeviceClass, EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import EasywaveConfigEntry, get_devices
from .const import (
    CONF_BUTTON_COUNT,
    CONF_DETECTED_BUTTON,
    CONF_ENTRY_TYPE,
    CONF_GROUPING_MODE,
    CONF_OPERATING_TYPE,
    ENTRY_TYPE_TRANSMITTER,
    TRANSMITTER_GROUPING_GROUP,
)
from .entity import EasywaveDeviceEntry, EasywaveTransmitterEntity

_BUTTON_SUFFIXES: list[str] = ["a", "b", "c", "d"]
_BUTTON_TRANSLATION_KEYS: list[str] = [
    "transmitter_button_a",
    "transmitter_button_b",
    "transmitter_button_c",
    "transmitter_button_d",
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EasywaveConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Easywave button event entities from transmitter subentries."""
    for subentry in get_devices(entry):
        if subentry.data.get(CONF_ENTRY_TYPE) != ENTRY_TYPE_TRANSMITTER:
            continue

        operating_type = str(subentry.data.get(CONF_OPERATING_TYPE, "1"))
        if operating_type != "1":
            continue

        grouping_mode = str(subentry.data.get(CONF_GROUPING_MODE, "single"))
        if grouping_mode == TRANSMITTER_GROUPING_GROUP:
            # Group mode is handled by the last-button SensorEntity in sensor.py.
            continue

        button_count: int = min(subentry.data.get(CONF_BUTTON_COUNT, 4), 4)
        if button_count == 1:
            detected: int = subentry.data.get(CONF_DETECTED_BUTTON, 0)
            entities: list[EasywaveButtonEvent] = [
                EasywaveButtonEvent(entry, subentry, detected, backward_compat=True)
            ]
        else:
            entities = [
                EasywaveButtonEvent(entry, subentry, i) for i in range(button_count)
            ]

        async_add_entities(entities)


class EasywaveButtonEvent(EasywaveTransmitterEntity, EventEntity):
    """EventEntity for a single physical button on a type-1 transmitter.

    Fires a ``pressed`` event on every button press and a ``released`` event
    when the button is released.  The ``released`` event is only fired by the
    entity whose button was most recently pressed, preventing spurious release
    events on sibling entities (the hardware always sends button=0 on release
    regardless of which button was pressed).
    """

    _attr_device_class = EventDeviceClass.BUTTON
    _attr_event_types = ["pressed", "released"]

    def __init__(
        self,
        entry: EasywaveConfigEntry,
        subentry: EasywaveDeviceEntry,
        button_index: int,
        *,
        backward_compat: bool = False,
    ) -> None:
        """Initialize the button event entity."""
        suffix = (
            "button" if backward_compat else f"button_{_BUTTON_SUFFIXES[button_index]}"
        )
        super().__init__(entry, subentry, suffix)
        self._button_index = button_index
        self._attr_translation_key = (
            "transmitter" if backward_compat else _BUTTON_TRANSLATION_KEYS[button_index]
        )
        self._is_pressed = False

    @callback
    def handle_telegram(self, info_type: int, button: int) -> None:
        """Fire an event from an incoming transmitter telegram."""
        if info_type == 0x01:  # PUSH
            if button != self._button_index:
                return
            self._is_pressed = True
            self._trigger_event("pressed")
            self.async_write_ha_state()
        elif info_type == 0x00:  # RELEASE
            if not self._is_pressed:
                # This entity was not the one that was pressed; ignore the
                # universal release telegram.
                return
            self._is_pressed = False
            self._trigger_event("released")
            self.async_write_ha_state()
