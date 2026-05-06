"""Switch platform for Easywave receivers."""

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import EasywaveConfigEntry, get_devices
from .const import (
    BUTTON_A,
    BUTTON_B,
    CONF_ENTRY_TYPE,
    CONF_RECEIVER_KIND,
    ENTRY_TYPE_RECEIVER,
    RECEIVER_KIND_HEATING,
    RECEIVER_KIND_SWITCH,
)
from .entity import EasywaveDeviceEntry, EasywaveReceiverEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EasywaveConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Easywave switch entities."""
    for subentry in get_devices(entry):
        entry_type = subentry.data.get(CONF_ENTRY_TYPE)

        if entry_type == ENTRY_TYPE_RECEIVER:
            receiver_kind = subentry.data.get(CONF_RECEIVER_KIND)
            if receiver_kind in (RECEIVER_KIND_SWITCH, RECEIVER_KIND_HEATING):
                async_add_entities(
                    [EasywaveReceiverSwitch(entry, subentry)],
                )


class EasywaveReceiverSwitch(EasywaveReceiverEntity, SwitchEntity, RestoreEntity):
    """Represents an Easywave receiver controlled via the RX11 gateway."""

    _attr_assumed_state = True

    def __init__(
        self, entry: EasywaveConfigEntry, subentry: EasywaveDeviceEntry
    ) -> None:
        """Initialize the switch."""
        super().__init__(entry, subentry, "switch")
        self._attr_is_on = False

        if subentry.data.get(CONF_RECEIVER_KIND) == RECEIVER_KIND_HEATING:
            self._attr_translation_key = "heating"
        else:
            self._attr_translation_key = "receiver"

    async def async_added_to_hass(self) -> None:
        """Restore the last known on/off state across restarts."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is not None and last_state.state in ("on", "off"):
            self._attr_is_on = last_state.state == "on"
            self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the receiver (send button A command)."""
        if await self._send_command(BUTTON_A):
            self._attr_is_on = True
            self.async_write_ha_state()
        else:
            _LOGGER.warning(
                "Failed to send ON command to receiver %d", self._gateway_index
            )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the receiver (send button B command)."""
        if await self._send_command(BUTTON_B):
            self._attr_is_on = False
            self.async_write_ha_state()
        else:
            _LOGGER.warning(
                "Failed to send OFF command to receiver %d", self._gateway_index
            )
