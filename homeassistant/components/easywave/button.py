"""Button platform for Easywave receivers."""

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import EasywaveConfigEntry, get_devices
from .const import (
    BUTTON_A,
    BUTTON_B,
    BUTTON_C,
    BUTTON_D,
    CONF_ENTRY_TYPE,
    CONF_RECEIVER_KIND,
    ENTRY_TYPE_RECEIVER,
    RECEIVER_KIND_UNIVERSAL,
)
from .entity import EasywaveDeviceEntry, EasywaveReceiverEntity

_LOGGER = logging.getLogger(__name__)

_UNIVERSAL_BUTTONS = [
    ("a", BUTTON_A),
    ("b", BUTTON_B),
    ("c", BUTTON_C),
    ("d", BUTTON_D),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EasywaveConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Easywave button entities from receiver subentries."""
    for subentry in get_devices(entry):
        if subentry.data.get(CONF_ENTRY_TYPE) != ENTRY_TYPE_RECEIVER:
            continue
        receiver_kind = subentry.data.get(CONF_RECEIVER_KIND)
        if receiver_kind == RECEIVER_KIND_UNIVERSAL:
            async_add_entities(
                [
                    EasywaveReceiverButton(entry, subentry, suffix, button_code)
                    for suffix, button_code in _UNIVERSAL_BUTTONS
                ],
            )


class EasywaveReceiverButton(EasywaveReceiverEntity, ButtonEntity):
    """Represents an Easywave receiver button (impulse or universal mode)."""

    def __init__(
        self,
        entry: EasywaveConfigEntry,
        subentry: EasywaveDeviceEntry,
        suffix: str,
        button_code: int,
    ) -> None:
        """Initialize the button."""
        super().__init__(entry, subentry, f"button_{suffix}")
        self._button_code = button_code

        self._attr_translation_key = f"universal_{suffix}"

    async def async_press(self) -> None:
        """Send the button command to the receiver."""
        if not await self._send_command(self._button_code):
            _LOGGER.warning(
                "Failed to send button %d command to receiver %d",
                self._button_code,
                self._gateway_index,
            )
