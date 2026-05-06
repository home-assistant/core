"""Cover platform for Easywave receivers."""

import logging
from typing import Any

from homeassistant.components.cover import (
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import EasywaveConfigEntry, get_devices
from .const import (
    BUTTON_A,
    BUTTON_B,
    BUTTON_C,
    CONF_ENTRY_TYPE,
    CONF_RECEIVER_KIND,
    ENTRY_TYPE_RECEIVER,
    RECEIVER_KIND_COVER,
    RECEIVER_KIND_MOTOR,
)
from .entity import EasywaveDeviceEntry, EasywaveReceiverEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EasywaveConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Easywave cover entities."""
    for subentry in get_devices(entry):
        entry_type = subentry.data.get(CONF_ENTRY_TYPE)

        if entry_type == ENTRY_TYPE_RECEIVER:
            receiver_kind = subentry.data.get(CONF_RECEIVER_KIND)
            if receiver_kind in (RECEIVER_KIND_COVER, RECEIVER_KIND_MOTOR):
                async_add_entities(
                    [EasywaveReceiverCover(entry, subentry)],
                )


class EasywaveReceiverCover(EasywaveReceiverEntity, CoverEntity, RestoreEntity):
    """Represents an Easywave cover/motor receiver controlled via the RX11 gateway."""

    _attr_assumed_state = True
    _attr_device_class = CoverDeviceClass.SHADE

    def __init__(
        self, entry: EasywaveConfigEntry, subentry: EasywaveDeviceEntry
    ) -> None:
        """Initialize the cover."""
        super().__init__(entry, subentry, "cover")
        receiver_kind = subentry.data[CONF_RECEIVER_KIND]
        self._supports_stop = receiver_kind == RECEIVER_KIND_MOTOR

        if self._supports_stop:
            self._attr_translation_key = "motor"
            self._attr_supported_features = (
                CoverEntityFeature.OPEN
                | CoverEntityFeature.CLOSE
                | CoverEntityFeature.STOP
            )
        else:
            self._attr_translation_key = "cover"
            self._attr_supported_features = (
                CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE
            )

        self._attr_is_closed = None

    async def async_added_to_hass(self) -> None:
        """Restore the last known open/closed state across restarts."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is None:
            return
        if last_state.state == "closed":
            self._attr_is_closed = True
        elif last_state.state == "open":
            self._attr_is_closed = False
        else:
            return
        self.async_write_ha_state()

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover (send button A command)."""
        if await self._send_command(BUTTON_A):
            self._attr_is_closed = False
            self.async_write_ha_state()
        else:
            _LOGGER.warning(
                "Failed to send OPEN command to receiver %d", self._gateway_index
            )

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover (send button B command)."""
        if await self._send_command(BUTTON_B):
            self._attr_is_closed = True
            self.async_write_ha_state()
        else:
            _LOGGER.warning(
                "Failed to send CLOSE command to receiver %d", self._gateway_index
            )

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover (send button C command)."""
        if not self._supports_stop:
            return
        if not await self._send_command(BUTTON_C):
            _LOGGER.warning(
                "Failed to send STOP command to receiver %d", self._gateway_index
            )
