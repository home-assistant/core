"""Update coordinator and WebSocket listener(s) for the Bang & Olufsen integration."""
# pylint: disable=raise-missing-from

from __future__ import annotations

from datetime import datetime
import logging

from mozart_api.models import (
    BeoRemoteButton,
    ButtonEvent,
    PlaybackContentMetadata,
    PlaybackError,
    PlaybackProgress,
    RenderingState,
    SoftwareUpdateState,
    Source,
    VolumeState,
    WebsocketNotificationTag,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE_ID, CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    BANGOLUFSEN_EVENT,
    BANGOLUFSEN_WEBSOCKET_EVENT,
    CONNECTION_STATUS,
    BangOlufsenVariables,
    WebSocketNotification,
    get_device,
)

_LOGGER = logging.getLogger(__name__)


class BangOlufsenWebsocket(BangOlufsenVariables):
    """The WebSocket listeners."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the WebSocket listeners."""

        BangOlufsenVariables.__init__(self, entry)

        self.hass = hass
        self._device: DeviceEntry | None = None

        # WebSocket callbacks
        self._client.get_on_connection(self.on_connection)
        self._client.get_on_connection_lost(self.on_connection_lost)

        self._client.get_beo_remote_button_notifications(
            self.on_beo_remote_button_notification
        )
        self._client.get_button_notifications(self.on_button_notification)
        self._client.get_notification_notifications(self.on_notification_notification)
        self._client.get_playback_error_notifications(
            self.on_playback_error_notification
        )
        self._client.get_playback_metadata_notifications(
            self.on_playback_metadata_notification
        )
        self._client.get_playback_progress_notifications(
            self.on_playback_progress_notification
        )
        self._client.get_playback_state_notifications(
            self.on_playback_state_notification
        )
        self._client.get_source_change_notifications(self.on_source_change_notification)
        self._client.get_volume_notifications(self.on_volume_notification)
        self._client.get_software_update_state_notifications(
            self.on_software_update_state
        )

        # Used for firing events and debugging
        self._client.get_all_notifications_raw(self.on_all_notifications_raw)

    def connect_websocket(self, _: datetime | None = None) -> None:
        """Start the notification WebSocket listeners."""
        if self._client.websocket_connected:
            return

        self._client.connect_notifications(remote_control=True)

    def disconnect(self) -> None:
        """Terminate the WebSocket connections and remove dispatchers."""
        self._client.disconnect_notifications()
        self._update_connection_status()

    def _update_connection_status(self) -> None:
        """Update all entities of the connection status."""
        async_dispatcher_send(
            self.hass,
            f"{self._unique_id}_{CONNECTION_STATUS}",
            self._client.websocket_connected,
        )

    def on_connection(self) -> None:
        """Handle WebSocket connection made."""
        _LOGGER.info("Connected to the %s notification channel", self._name)
        self._update_connection_status()

    def on_connection_lost(self) -> None:
        """Handle WebSocket connection lost."""
        _LOGGER.error("Lost connection to the %s", self._name)
        self._update_connection_status()

    def on_beo_remote_button_notification(self, notification: BeoRemoteButton) -> None:
        """Send beo_remote_button dispatch."""
        if not isinstance(self._device, DeviceEntry):
            self._device = get_device(self.hass, self._unique_id)

        assert isinstance(self._device, DeviceEntry)

        if notification.type == "KeyPress":
            # Trigger the device trigger
            self.hass.bus.async_fire(
                BANGOLUFSEN_EVENT,
                event_data={
                    CONF_TYPE: f"{notification.key}_{notification.type}",
                    CONF_DEVICE_ID: self._device.id,
                },
            )

    def on_button_notification(self, notification: ButtonEvent) -> None:
        """Send button dispatch."""
        if not isinstance(self._device, DeviceEntry):
            self._device = get_device(self.hass, self._unique_id)

        assert isinstance(self._device, DeviceEntry)

        # Trigger the device trigger
        self.hass.bus.async_fire(
            BANGOLUFSEN_EVENT,
            event_data={
                CONF_TYPE: f"{notification.button}_{notification.state}",
                CONF_DEVICE_ID: self._device.id,
            },
        )

    def on_notification_notification(
        self, notification: WebsocketNotificationTag
    ) -> None:
        """Send notification dispatch."""

        if WebSocketNotification.REMOTE_MENU_CHANGED in notification.value:
            async_dispatcher_send(
                self.hass,
                f"{self._unique_id}_{WebSocketNotification.REMOTE_MENU_CHANGED}",
            )

        elif WebSocketNotification.CONFIGURATION in notification.value:
            async_dispatcher_send(
                self.hass,
                f"{self._unique_id}_{WebSocketNotification.CONFIGURATION}",
                notification,
            )

        elif WebSocketNotification.BLUETOOTH_DEVICES in notification.value:
            async_dispatcher_send(
                self.hass,
                f"{self._unique_id}_{WebSocketNotification.BLUETOOTH_DEVICES}",
            )

        elif WebSocketNotification.REMOTE_CONTROL_DEVICES in notification.value:
            async_dispatcher_send(
                self.hass,
                f"{self._unique_id}_{WebSocketNotification.BLUETOOTH_DEVICES}",
            )

        elif WebSocketNotification.BEOLINK in notification.value:
            async_dispatcher_send(
                self.hass,
                f"{self._unique_id}_{WebSocketNotification.BEOLINK}",
            )

    def on_playback_error_notification(self, notification: PlaybackError) -> None:
        """Send playback_error dispatch."""
        async_dispatcher_send(
            self.hass,
            f"{self._unique_id}_{WebSocketNotification.PLAYBACK_ERROR}",
            notification,
        )

    def on_playback_metadata_notification(
        self, notification: PlaybackContentMetadata
    ) -> None:
        """Send playback_metadata dispatch."""
        async_dispatcher_send(
            self.hass,
            f"{self._unique_id}_{WebSocketNotification.PLAYBACK_METADATA}",
            notification,
        )

    def on_playback_progress_notification(self, notification: PlaybackProgress) -> None:
        """Send playback_progress dispatch."""
        async_dispatcher_send(
            self.hass,
            f"{self._unique_id}_{WebSocketNotification.PLAYBACK_PROGRESS}",
            notification,
        )

    def on_playback_state_notification(self, notification: RenderingState) -> None:
        """Send playback_state dispatch."""
        async_dispatcher_send(
            self.hass,
            f"{self._unique_id}_{WebSocketNotification.PLAYBACK_STATE}",
            notification,
        )

    def on_source_change_notification(self, notification: Source) -> None:
        """Send source_change dispatch."""
        async_dispatcher_send(
            self.hass,
            f"{self._unique_id}_{WebSocketNotification.SOURCE_CHANGE}",
            notification,
        )

    def on_volume_notification(self, notification: VolumeState) -> None:
        """Send volume dispatch."""
        async_dispatcher_send(
            self.hass,
            f"{self._unique_id}_{WebSocketNotification.VOLUME}",
            notification,
        )

    def on_software_update_state(self, notification: SoftwareUpdateState) -> None:
        """Check device sw version."""

        # Get software version.
        software_status = self._client.get_softwareupdate_status(async_req=True).get()

        # Update the HA device if the sw version does not match
        if not isinstance(self._device, DeviceEntry):
            self._device = get_device(self.hass, self._unique_id)

        assert isinstance(self._device, DeviceEntry)

        if software_status.software_version != self._device.sw_version:
            device_registry = dr.async_get(self.hass)

            device_registry.async_update_device(
                device_id=self._device.id,
                sw_version=software_status.software_version,
            )

    def on_all_notifications_raw(self, notification: dict) -> None:
        """Receive all notifications."""
        if not isinstance(self._device, DeviceEntry):
            self._device = get_device(self.hass, self._unique_id)

        assert isinstance(self._device, DeviceEntry)

        # Add the device_id and serial_number to the notification
        notification["device_id"] = self._device.id
        notification["serial_number"] = int(self._unique_id)

        _LOGGER.debug("%s", notification)
        self.hass.bus.async_fire(BANGOLUFSEN_WEBSOCKET_EVENT, notification)
