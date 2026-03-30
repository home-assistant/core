"""Event platform for Huawei LTE integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.event import EventEntity, EventEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import Router
from .const import CONF_UNAUTHENTICATED_MODE, DOMAIN, KEY_SMS_SMS_LIST, SMS_EVENT_SIGNAL
from .entity import HuaweiLteBaseEntityWithDevice


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the event platform."""
    router = hass.data[DOMAIN].routers[config_entry.entry_id]
    # Only add SMS event entity in authenticated mode; unauthenticated mode
    # does not have access to KEY_SMS_SMS_LIST.
    if not config_entry.options.get(CONF_UNAUTHENTICATED_MODE):
        async_add_entities([HuaweiLteSmsReceivedEvent(router)])


class HuaweiLteSmsReceivedEvent(HuaweiLteBaseEntityWithDevice, EventEntity):
    """Event entity for incoming SMS messages."""

    _attr_translation_key = "sms_received"
    _attr_event_types = ["sms_received"]

    def __init__(self, router: Router) -> None:
        """Initialize."""
        super().__init__(router)
        self.entity_description = EventEntityDescription(
            key="sms_received",
            translation_key="sms_received",
        )

    @property
    def _device_unique_id(self) -> str:
        return "sms_received"

    async def async_added_to_hass(self) -> None:
        """Subscribe to SMS event signal."""
        await super().async_added_to_hass()
        self.router.subscriptions[KEY_SMS_SMS_LIST].append("event/sms_received")
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{SMS_EVENT_SIGNAL}_{self.router.config_entry.unique_id}",
                self._async_handle_event,
            )
        )

    async def async_will_remove_from_hass(self) -> None:
        """Unsubscribe from SMS data on remove."""
        await super().async_will_remove_from_hass()
        self.router.subscriptions[KEY_SMS_SMS_LIST].remove("event/sms_received")

    @callback
    def _async_handle_event(self, event_data: dict[str, Any]) -> None:
        """Handle incoming SMS event."""
        self._trigger_event("sms_received", event_data)
        self.async_write_ha_state()
