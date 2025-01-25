"""Update coordinator and WebSocket listener(s) for the Bang & Olufsen integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from mozart_api.models import (
    ButtonEvent,
    ListeningModeProps,
    PlaybackContentMetadata,
    PlaybackError,
    PlaybackProgress,
    RenderingState,
    SoftwareUpdateState,
    Source,
    VolumeState,
    WebsocketNotificationTag,
)
from mozart_api.mozart_client import BaseWebSocketResponse, MozartClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.util.enum import try_parse_enum

from .const import (
    BANG_OLUFSEN_WEBSOCKET_EVENT,
    CONNECTION_STATUS,
    EVENT_TRANSLATION_MAP,
    WebsocketNotification,
)
from .entity import BangOlufsenBase
from .util import get_device

_LOGGER = logging.getLogger(__name__)


class BangOlufsenWebsocket(BangOlufsenBase):
    """The WebSocket listeners."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, client: MozartClient
    ) -> None:
        """Initialize the WebSocket listeners."""

        BangOlufsenBase.__init__(self, entry, client)

        self.hass = hass
        self._device = get_device(hass, self._unique_id)

        # WebSocket callbacks
        self._client.get_notification_notifications(self.on_notification_notification)
        self._client.get_on_connection_lost(self.on_connection_lost)
        self._client.get_on_connection(self.on_connection)
        self._client.get_active_listening_mode_notifications(
            self.on_active_listening_mode
        )
        self._client.get_button_notifications(self.on_button_notification)

        self._client.get_playback_error_notifications(
            self.on_playback_error_notification
        )
        self._client.get_playback_metadata_notifications(
            self.on_playback_metadata_notification
        )
        self._client.get_playback_progress_notifications(
            self.on_playback_progress_notification
        )
        self._client.get_playback_source_notifications(
            self.on_playback_source_notification
        )
        self._client.get_playback_state_notifications(
            self.on_playback_state_notification
        )
        self._client.get_software_update_state_notifications(
            self.on_software_update_state
        )
        self._client.get_source_change_notifications(self.on_source_change_notification)
        self._client.get_volume_notifications(self.on_volume_notification)

        # Used for firing events and debugging
        self._client.get_all_notifications_raw(self.on_all_notifications_raw)

    def _update_connection_status(self) -> None:
        """Update all entities of the connection status."""
        async_dispatcher_send(
            self.hass,
            f"{self._unique_id}_{CONNECTION_STATUS}",
            self._client.websocket_connected,
        )

    def on_connection(self) -> None:
        """Handle WebSocket connection made."""
        _LOGGER.debug("Connected to the %s notification channel", self.entry.title)
        self._update_connection_status()

    def on_connection_lost(self) -> None:
        """Handle WebSocket connection lost."""
        _LOGGER.error("Lost connection to the %s", self.entry.title)
        self._update_connection_status()

    def on_active_listening_mode(self, notification: ListeningModeProps) -> None:
        """Send active_listening_mode dispatch."""
        async_dispatcher_send(
            self.hass,
            f"{self._unique_id}_{WebsocketNotification.ACTIVE_LISTENING_MODE}",
            notification,
        )

    def on_button_notification(self, notification: ButtonEvent) -> None:
        """Send button dispatch."""
        # State is expected to always be available.
        if TYPE_CHECKING:
            assert notification.state

        # Send to event entity
        async_dispatcher_send(
            self.hass,
            f"{self._unique_id}_{WebsocketNotification.BUTTON}_{notification.button}",
            EVENT_TRANSLATION_MAP[notification.state],
        )

    def on_notification_notification(
        self, notification: WebsocketNotificationTag
    ) -> None:
        """Send notification dispatch."""
        # Try to match the notification type with available WebsocketNotification members
        notification_type = try_parse_enum(WebsocketNotification, notification.value)

        if notification_type in (
            WebsocketNotification.BEOLINK_PEERS,
            WebsocketNotification.BEOLINK_LISTENERS,
            WebsocketNotification.BEOLINK_AVAILABLE_LISTENERS,
        ):
            async_dispatcher_send(
                self.hass,
                f"{self._unique_id}_{WebsocketNotification.BEOLINK}",
            )
        elif notification_type is WebsocketNotification.CONFIGURATION:
            async_dispatcher_send(
                self.hass,
                f"{self._unique_id}_{WebsocketNotification.CONFIGURATION}",
            )
        elif notification_type is WebsocketNotification.REMOTE_MENU_CHANGED:
            async_dispatcher_send(
                self.hass,
                f"{self._unique_id}_{WebsocketNotification.REMOTE_MENU_CHANGED}",
            )

    def on_playback_error_notification(self, notification: PlaybackError) -> None:
        """Send playback_error dispatch."""
        async_dispatcher_send(
            self.hass,
            f"{self._unique_id}_{WebsocketNotification.PLAYBACK_ERROR}",
            notification,
        )

    def on_playback_metadata_notification(
        self, notification: PlaybackContentMetadata
    ) -> None:
        """Send playback_metadata dispatch."""
        async_dispatcher_send(
            self.hass,
            f"{self._unique_id}_{WebsocketNotification.PLAYBACK_METADATA}",
            notification,
        )

    def on_playback_progress_notification(self, notification: PlaybackProgress) -> None:
        """Send playback_progress dispatch."""
        async_dispatcher_send(
            self.hass,
            f"{self._unique_id}_{WebsocketNotification.PLAYBACK_PROGRESS}",
            notification,
        )

    def on_playback_state_notification(self, notification: RenderingState) -> None:
        """Send playback_state dispatch."""
        async_dispatcher_send(
            self.hass,
            f"{self._unique_id}_{WebsocketNotification.PLAYBACK_STATE}",
            notification,
        )

    def on_playback_source_notification(self, notification: Source) -> None:
        """Send playback_source dispatch."""
        async_dispatcher_send(
            self.hass,
            f"{self._unique_id}_{WebsocketNotification.PLAYBACK_SOURCE}",
            notification,
        )

    def on_source_change_notification(self, notification: Source) -> None:
        """Send source_change dispatch."""
        async_dispatcher_send(
            self.hass,
            f"{self._unique_id}_{WebsocketNotification.SOURCE_CHANGE}",
            notification,
        )

    def on_volume_notification(self, notification: VolumeState) -> None:
        """Send volume dispatch."""
        async_dispatcher_send(
            self.hass,
            f"{self._unique_id}_{WebsocketNotification.VOLUME}",
            notification,
        )

    async def on_software_update_state(self, notification: SoftwareUpdateState) -> None:
        """Check device sw version."""
        software_status = await self._client.get_softwareupdate_status()

        # Update the HA device if the sw version does not match
        if software_status.software_version != self._device.sw_version:
            device_registry = dr.async_get(self.hass)

            device_registry.async_update_device(
                device_id=self._device.id,
                sw_version=software_status.software_version,
            )

    def on_all_notifications_raw(self, notification: BaseWebSocketResponse) -> None:
        """Receive all notifications."""
        debug_notification = {
            "device_id": self._device.id,
            "serial_number": int(self._unique_id),
            **notification,
        }

        _LOGGER.debug("%s", debug_notification)
        self.hass.bus.async_fire(BANG_OLUFSEN_WEBSOCKET_EVENT, debug_notification)
