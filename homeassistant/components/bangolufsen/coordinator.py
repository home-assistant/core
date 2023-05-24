"""Update coordinator and WebSocket listener(s) for the Bang & Olufsen integration."""
# pylint: disable=raise-missing-from

from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import TypedDict

from mozart_api.exceptions import ApiException
from mozart_api.models import (
    BatteryState,
    BeoRemoteButton,
    ButtonEvent,
    ListeningModeProps,
    PlaybackContentMetadata,
    PlaybackError,
    PlaybackProgress,
    Preset,
    RenderingState,
    SoftwareUpdateState,
    SoundSettings,
    Source,
    SpeakerGroupOverview,
    VolumeState,
    WebsocketNotificationTag,
)
from urllib3.exceptions import MaxRetryError, NewConnectionError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE_ID, CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    BANGOLUFSEN_EVENT,
    BANGOLUFSEN_WEBSOCKET_EVENT,
    CONNECTION_STATUS,
    BangOlufsenVariables,
    WebSocketNotification,
    get_device,
)

_LOGGER = logging.getLogger(__name__)


class CoordinatorData(TypedDict):
    """TypedDict for coordinator data."""

    favourites: dict[str, Preset]


class BangOlufsenCoordinator(DataUpdateCoordinator, BangOlufsenVariables):
    """The entity coordinator and WebSocket listener(s)."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the entity coordinator."""
        DataUpdateCoordinator.__init__(
            self,
            hass,
            _LOGGER,
            name="coordinator",
            update_interval=timedelta(seconds=60),
        )
        BangOlufsenVariables.__init__(self, entry)

        self._coordinator_data: CoordinatorData = {"favourites": {}}

        self._device: DeviceEntry | None = None

        # WebSocket callbacks
        self._client.get_on_connection(self.on_connection)
        self._client.get_on_connection_lost(self.on_connection_lost)
        self._client.get_active_listening_mode_notifications(
            self.on_active_listening_mode
        )
        self._client.get_active_speaker_group_notifications(
            self.on_active_speaker_group
        )
        self._client.get_battery_notifications(self.on_battery_notification)
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
        self._client.get_sound_settings_notifications(
            self.on_sound_settings_notification
        )
        self._client.get_source_change_notifications(self.on_source_change_notification)
        self._client.get_volume_notifications(self.on_volume_notification)
        self._client.get_software_update_state_notifications(
            self.on_software_update_state
        )

        # Used for firing events and debugging
        self._client.get_all_notifications_raw(self.on_all_notifications_raw)

    async def _update_variables(self) -> None:
        """Update the coordinator data."""
        favourites = self._client.get_presets(async_req=True, _request_timeout=5).get()

        self._coordinator_data = {"favourites": favourites}

    async def _async_update_data(self) -> CoordinatorData:
        """Get all information needed by the polling entities."""
        if not self.last_update_success:
            raise UpdateFailed

        # Try to update coordinator_data.
        try:
            await self._update_variables()
            return self._coordinator_data

        except (
            MaxRetryError,
            NewConnectionError,
            ApiException,
            ConnectionResetError,
        ):
            raise UpdateFailed

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
        self.last_update_success = self._client.websocket_connected
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

    def on_active_listening_mode(self, notification: ListeningModeProps) -> None:
        """Send active_listening_mode dispatch."""
        async_dispatcher_send(
            self.hass,
            f"{self._unique_id}_{WebSocketNotification.ACTIVE_LISTENING_MODE}",
            notification,
        )

    def on_active_speaker_group(self, notification: SpeakerGroupOverview) -> None:
        """Send active_speaker_group dispatch."""
        async_dispatcher_send(
            self.hass,
            f"{self._unique_id}_{WebSocketNotification.ACTIVE_SPEAKER_GROUP}",
            notification,
        )

    def on_battery_notification(self, notification: BatteryState) -> None:
        """Send battery dispatch."""
        async_dispatcher_send(
            self.hass,
            f"{self._unique_id}_{WebSocketNotification.BATTERY}",
            notification,
        )

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

        if WebSocketNotification.PROXIMITY in notification.value:
            async_dispatcher_send(
                self.hass,
                f"{self._unique_id}_{WebSocketNotification.PROXIMITY}",
                notification,
            )

        elif WebSocketNotification.REMOTE_MENU_CHANGED in notification.value:
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

    def on_sound_settings_notification(self, notification: SoundSettings) -> None:
        """Send sound_settings dispatch."""
        async_dispatcher_send(
            self.hass,
            f"{self._unique_id}_{WebSocketNotification.SOUND_SETTINGS}",
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
