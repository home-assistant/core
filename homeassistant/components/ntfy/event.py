"""Event platform for ntfy integration."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import TYPE_CHECKING

from aiontfy import Event, Notification
from aiontfy.exceptions import (
    NtfyConnectionError,
    NtfyForbiddenError,
    NtfyHTTPError,
    NtfyTimeoutError,
)

from homeassistant.components.event import EventEntity, EventEntityDescription
from homeassistant.config_entries import ConfigSubentry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_MESSAGE, CONF_PRIORITY, CONF_TAGS, CONF_TITLE
from .coordinator import NtfyConfigEntry
from .entity import NtfyBaseEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0

SCAN_INTERVAL = timedelta(seconds=10)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: NtfyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the event platform."""

    for subentry_id, subentry in config_entry.subentries.items():
        async_add_entities(
            [NtfyEventEntity(config_entry, subentry)], config_subentry_id=subentry_id
        )


class NtfyEventEntity(NtfyBaseEntity, EventEntity):
    """An event entity."""

    entity_description = EventEntityDescription(
        key="subscribe",
        translation_key="subscribe",
        name=None,
        event_types=["triggered"],
    )

    def __init__(
        self,
        config_entry: NtfyConfigEntry,
        subentry: ConfigSubentry,
    ) -> None:
        """Initialize the entity."""
        super().__init__(config_entry, subentry)
        self._ws: asyncio.Task | None = None

    @callback
    def _async_handle_event(self, notification: Notification) -> None:
        """Handle the ntfy event."""
        if notification.topic == self.topic and notification.event is Event.MESSAGE:
            event = (
                f"{notification.title}: {notification.message}"
                if notification.title
                else notification.message
            )
            if TYPE_CHECKING:
                assert event
            self._attr_event_types = [event]
            self._trigger_event(event, notification.to_dict())
            self.async_write_ha_state()

    async def async_update(self) -> None:
        """Connect websocket."""
        try:
            if self._ws and (exc := self._ws.exception()):
                raise exc
        except asyncio.InvalidStateError:
            self._attr_available = True
        except asyncio.CancelledError:
            if self._attr_available:
                _LOGGER.exception(
                    "Connection to ntfy service was terminated unexpectedly"
                )
            self._attr_available = False
        except NtfyForbiddenError:
            if self._attr_available:
                _LOGGER.error("Failed to subscribe to topic. Topic is protected")
            self._attr_available = False
        except NtfyHTTPError as e:
            if self._attr_available:
                _LOGGER.exception(
                    "Failed to connect to ntfy service due to a server error: %s (%s)",
                    e.error,
                    e.link,
                )
            self._attr_available = False
        except NtfyConnectionError:
            if self._attr_available:
                _LOGGER.exception(
                    "Failed to connect to ntfy service due to a connection error"
                )
            self._attr_available = False
        except NtfyTimeoutError:
            if self._attr_available:
                _LOGGER.exception(
                    "Failed to connect to ntfy service due to a connection timeout"
                )
            self._attr_available = False
        finally:
            if self._ws is None or self._ws.done():
                self._ws = self.config_entry.async_create_background_task(
                    hass=self.hass,
                    target=self.ntfy.subscribe(
                        topics=[self.topic],
                        callback=self._async_handle_event,
                        title=self.subentry.data.get(CONF_TITLE),
                        message=self.subentry.data.get(CONF_MESSAGE),
                        priority=self.subentry.data.get(CONF_PRIORITY),
                        tags=self.subentry.data.get(CONF_TAGS),
                    ),
                    name="ntfy_websocket",
                )

    @property
    def entity_picture(self) -> str | None:
        """Return the entity picture to use in the frontend, if any."""

        return self.state_attributes.get("icon") or super().entity_picture
