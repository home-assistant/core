"""Event platform for ntfy integration."""

import asyncio
import logging
from typing import TYPE_CHECKING, override

from aiontfy import Event, Notification
from aiontfy.exceptions import (
    NtfyConnectionError,
    NtfyForbiddenError,
    NtfyHTTPError,
    NtfyTimeoutError,
)

from homeassistant.components.event import (
    DOMAIN as EVENT_DOMAIN,
    EventEntity,
    EventEntityDescription,
)
from homeassistant.config_entries import ConfigSubentry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_MESSAGE, CONF_PRIORITY, CONF_TAGS, CONF_TITLE, DOMAIN
from .coordinator import NtfyConfigEntry
from .entity import NtfyBaseEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0
RECONNECT_INTERVAL = 10


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: NtfyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the event platform."""

    # Entities disabled while the entry was not loaded didn't delete their issue
    for entity_entry in er.async_entries_for_config_entry(
        er.async_get(hass), config_entry.entry_id
    ):
        if (
            entity_entry.domain == EVENT_DOMAIN
            and entity_entry.disabled
            and entity_entry.config_subentry_id is not None
        ):
            ir.async_delete_issue(
                hass,
                DOMAIN,
                _topic_protected_issue_id(
                    config_entry.entry_id, entity_entry.config_subentry_id
                ),
            )

    for subentry_id, subentry in config_entry.subentries.items():
        async_add_entities(
            [NtfyEventEntity(config_entry, subentry)], config_subentry_id=subentry_id
        )


def _topic_protected_issue_id(entry_id: str, subentry_id: str) -> str:
    """Return the id of the protected topic issue of a topic subentry."""
    return f"topic_protected_{entry_id}_{subentry_id}"


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
        self._topic_protected_issue_id = _topic_protected_issue_id(
            config_entry.entry_id, subentry.subentry_id
        )

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

    @override
    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""

        self.config_entry.async_create_background_task(
            self.hass,
            self.ws_connect(),
            "websocket_watchdog",
        )

    @override
    async def async_removed_from_registry(self) -> None:
        """Run when entity has been removed from the entity registry."""
        ir.async_delete_issue(self.hass, DOMAIN, self._topic_protected_issue_id)

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        # Core hides issues of a disabled config entry, keep them and their ignore
        if self.registry_entry is not None and self.registry_entry.disabled_by not in (
            None,
            er.RegistryEntryDisabler.CONFIG_ENTRY,
        ):
            ir.async_delete_issue(self.hass, DOMAIN, self._topic_protected_issue_id)

    async def ws_connect(self) -> None:
        """Connect websocket."""
        while True:
            try:
                if self._ws and (exc := self._ws.exception()):
                    raise exc  # noqa: TRY301
            except asyncio.InvalidStateError:
                self._attr_available = True
                ir.async_delete_issue(self.hass, DOMAIN, self._topic_protected_issue_id)
            except asyncio.CancelledError:
                self._attr_available = False
                return
            except NtfyForbiddenError:
                if self._attr_available:
                    _LOGGER.error(
                        "Failed to subscribe to topic %s. Topic is protected",
                        self.topic,
                    )
                self._attr_available = False
                ir.async_create_issue(
                    self.hass,
                    DOMAIN,
                    self._topic_protected_issue_id,
                    config_entry_id=self.config_entry.entry_id,
                    config_subentry_id=self.subentry.subentry_id,
                    is_fixable=True,
                    severity=ir.IssueSeverity.ERROR,
                    translation_key="topic_protected",
                    translation_placeholders={
                        "topic": self.topic,
                        "name": self.config_entry.title,
                    },
                    data={
                        "unique_id": self.unique_id,
                        "topic": self.topic,
                        "name": self.config_entry.title,
                    },
                )
                return
            except NtfyHTTPError as e:
                if self._attr_available:
                    _LOGGER.error(
                        "Failed to connect to ntfy service"
                        " due to a server error: %s (%s)",
                        e.error,
                        e.link,
                    )
                self._attr_available = False
            except NtfyConnectionError:
                if self._attr_available:
                    _LOGGER.error(
                        "Failed to connect to ntfy service due to a connection error"
                    )
                self._attr_available = False
            except NtfyTimeoutError:
                if self._attr_available:
                    _LOGGER.error(
                        "Failed to connect to ntfy service due to a connection timeout"
                    )
                self._attr_available = False
            except Exception:
                if self._attr_available:
                    _LOGGER.exception(
                        "Failed to connect to ntfy service"
                        " due to an unexpected exception"
                    )
                self._attr_available = False
            finally:
                self.async_write_ha_state()
            if self._ws is None or self._ws.done():
                self._ws = self.config_entry.async_create_background_task(
                    self.hass,
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
            await asyncio.sleep(RECONNECT_INTERVAL)

    @property
    @override
    def entity_picture(self) -> str | None:
        """Return the entity picture to use in the frontend, if any."""

        return self.state_attributes.get("icon") or super().entity_picture
