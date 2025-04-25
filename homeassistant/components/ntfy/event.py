"""Event platform for ntfy integration."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import TYPE_CHECKING

from aiontfy import Event, Notification
from aiontfy.exceptions import NtfyConnectionError, NtfyHTTPError, NtfyTimeoutError
from yarl import URL

from homeassistant.components.event import EventEntity, EventEntityDescription
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import CONF_NAME, CONF_URL
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import NtfyConfigEntry
from .const import CONF_TOPIC, DOMAIN

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 10

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


class NtfyEventEntity(EventEntity):
    """An event entity."""

    _attr_has_entity_name = True
    entity_description = EventEntityDescription(
        key="subscribe",
        translation_key="subscribe",
        name=None,
        has_entity_name=True,
        event_types=["triggered"],
    )

    def __init__(
        self,
        config_entry: NtfyConfigEntry,
        subentry: ConfigSubentry,
    ) -> None:
        """Initialize the entity."""
        self.topic = subentry.data[CONF_TOPIC]

        self._attr_unique_id = f"{config_entry.entry_id}_{subentry.subentry_id}_{self.entity_description.key}"

        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            manufacturer="ntfy LLC",
            model="ntfy",
            name=subentry.data.get(CONF_NAME, self.topic),
            configuration_url=URL(config_entry.data[CONF_URL]) / self.topic,
            identifiers={(DOMAIN, f"{config_entry.entry_id}_{subentry.subentry_id}")},
        )
        self.ntfy = config_entry.runtime_data
        self._ws: asyncio.Task | None = None
        self.config_entry = config_entry
        self._connectivity_check = False

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
            self._connectivity_check = True
        except asyncio.CancelledError:
            if self._connectivity_check:
                _LOGGER.exception(
                    "Connection to ntfy service was terminated unexpectedly"
                )
            self._connectivity_check = False
        except NtfyHTTPError as e:
            if self._connectivity_check:
                _LOGGER.exception(
                    "Failed to connect to ntfy service due to a server error: %s (%s)",
                    e.error,
                    e.link,
                )
            self._connectivity_check = False
        except NtfyConnectionError:
            if self._connectivity_check:
                _LOGGER.exception(
                    "Failed to connect to ntfy service due to a connection error"
                )
            self._connectivity_check = False
        except NtfyTimeoutError:
            if self._connectivity_check:
                _LOGGER.exception(
                    "Failed to connect to ntfy service due to a connection timeout"
                )
            self._connectivity_check = False

        finally:
            if self._ws is None or self._ws.done():
                self._ws = self.config_entry.async_create_background_task(
                    hass=self.hass,
                    target=self.ntfy.subscribe(
                        topics=[self.topic], callback=self._async_handle_event
                    ),
                    name="ntfy_websocket",
                )
        await super().async_added_to_hass()

    @property
    def entity_picture(self) -> str | None:
        """Return the entity picture to use in the frontend, if any."""

        return self.state_attributes.get("icon") or super().entity_picture

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._connectivity_check
