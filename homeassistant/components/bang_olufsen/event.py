"""Event entities for the Bang & Olufsen integration."""

from __future__ import annotations

from homeassistant.components.event import EventDeviceClass, EventEntity
from homeassistant.const import CONF_MODEL
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import BangOlufsenConfigEntry
from .const import (
    CONNECTION_STATUS,
    DEVICE_BUTTON_EVENTS,
    DEVICE_BUTTONS,
    MODEL_SUPPORT_DEVICE_BUTTONS,
    MODEL_SUPPORT_MAP,
    WebsocketNotification,
)
from .entity import BangOlufsenEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BangOlufsenConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Sensor entities from config entry."""

    if config_entry.data[CONF_MODEL] in MODEL_SUPPORT_MAP[MODEL_SUPPORT_DEVICE_BUTTONS]:
        async_add_entities(
            BangOlufsenButtonEvent(config_entry, button_type)
            for button_type in DEVICE_BUTTONS
        )


class BangOlufsenButtonEvent(BangOlufsenEntity, EventEntity):
    """Event class for Button events."""

    _attr_device_class = EventDeviceClass.BUTTON
    _attr_entity_registry_enabled_default = False
    _attr_event_types = DEVICE_BUTTON_EVENTS

    def __init__(self, config_entry: BangOlufsenConfigEntry, button_type: str) -> None:
        """Initialize Button."""
        super().__init__(config_entry, config_entry.runtime_data.client)

        self._attr_unique_id = f"{self._unique_id}_{button_type}"

        # Make the native button name Home Assistant compatible
        self._attr_translation_key = button_type.lower()

        self._button_type = button_type

    async def async_added_to_hass(self) -> None:
        """Listen to WebSocket button events."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{self._unique_id}_{CONNECTION_STATUS}",
                self._async_update_connection_state,
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{self._unique_id}_{WebsocketNotification.BUTTON}_{self._button_type}",
                self._async_handle_event,
            )
        )

    @callback
    def _async_handle_event(self, event: str) -> None:
        """Handle event."""
        self._trigger_event(event)
        self.async_write_ha_state()
