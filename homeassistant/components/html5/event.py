"""Event platform for HTML5 integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.event import EventEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import ATTR_ACTION, ATTR_DATA, ATTR_TAG, DOMAIN, REGISTRATIONS_FILE
from .entity import HTML5Entity
from .notify import _load_config

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the event entity platform."""

    json_path = hass.config.path(REGISTRATIONS_FILE)
    registrations = await hass.async_add_executor_job(_load_config, json_path)

    session = async_get_clientsession(hass)
    async_add_entities(
        HTML5EventEntity(config_entry, target, registrations, session, json_path)
        for target in registrations
    )


class HTML5EventEntity(HTML5Entity, EventEntity):
    """Representation of an event entity."""

    _key = "event"
    _attr_event_types = ["clicked", "received", "closed"]
    _attr_translation_key = "event"

    @callback
    def _async_handle_event(
        self, target: str, event_type: str, event_data: dict[str, Any]
    ) -> None:
        """Handle the event."""

        if target == self.target:
            self._trigger_event(
                event_type,
                {
                    **event_data.get(ATTR_DATA, {}),
                    ATTR_ACTION: event_data.get(ATTR_ACTION),
                    ATTR_TAG: event_data.get(ATTR_TAG),
                },
            )
            self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register event callback."""

        self.async_on_remove(
            async_dispatcher_connect(self.hass, DOMAIN, self._async_handle_event)
        )
