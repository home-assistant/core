"""Main Matrix bot implementation."""

from __future__ import annotations

import logging
import os

from nio import AsyncClient, AsyncClientConfig, MegolmEvent
from nio.events.room_events import RoomMessageText
from nio.events.to_device import KeyVerificationEvent

from homeassistant.const import EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event as HassEvent, HomeAssistant

from .auth import MatrixAuth
from .events import MatrixEvents
from .messages import MatrixMessages
from .rooms import MatrixRooms
from .types import ConfigCommand, RoomAnyID, RoomID

_LOGGER = logging.getLogger(__name__)

SESSION_FILE = ".matrix.conf"


class MatrixBot:
    """The Matrix Bot."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_file: str,
        homeserver: str,
        verify_ssl: bool,
        username: str,
        password: str,
        device_id: str,
        listening_rooms: list[RoomAnyID],
        commands: list[ConfigCommand],
    ) -> None:
        """Set up the client."""
        self.hass = hass
        self._mx_id = username
        self._password = password
        self._device_id = device_id

        # Initialize components
        self._auth = MatrixAuth(hass, config_file)

        # Set up client
        store_path = os.path.join(os.path.dirname(config_file), ".matrix_store")
        os.makedirs(store_path, exist_ok=True)

        config = AsyncClientConfig(
            max_limit_exceeded=30,
            max_timeouts=30,
            backoff_factor=0.1,
            store_sync_tokens=True,
            store_name="ha_matrix_store",
            encryption_enabled=True,
        )

        self._client = AsyncClient(
            homeserver=homeserver,
            user=self._mx_id,
            device_id=self._device_id,
            store_path=store_path,
            ssl=verify_ssl,
            config=config,
        )

        # Initialize room and event management
        self._listening_rooms: dict[RoomAnyID, RoomID] = {}
        self._rooms = MatrixRooms(self.hass, self._client, self._listening_rooms)
        self._events = MatrixEvents(
            hass, self._mx_id, self._client, {}, {}, self._listening_rooms
        )
        self._messages = MatrixMessages(hass, self._client, self._listening_rooms)

        # Store commands for later loading
        self._unparsed_commands = commands

        # Set up event handlers
        async def stop_client(event: HassEvent) -> None:
            """Run once when Home Assistant stops."""
            if self._client is not None:
                await self._client.close()

        self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, stop_client)

        async def handle_startup(event: HassEvent) -> None:
            """Run once when Home Assistant finished startup."""
            await self._auth.get_auth_tokens()
            await self._auth.login(self._client, self._mx_id, self._password)
            await self._rooms.resolve_room_aliases(listening_rooms)
            self._events.load_commands(commands, self._listening_rooms)
            await self._rooms.join_rooms()

            # Sync once so that we don't respond to past events.
            _LOGGER.debug("Starting initial sync for %s", self._mx_id)
            await self._client.sync(timeout=30_000)
            _LOGGER.debug("Finished initial sync for %s", self._mx_id)

            self._client.add_event_callback(
                self._events.handle_room_message, RoomMessageText
            )
            self._client.add_event_callback(
                self._events.decryption_failure, MegolmEvent
            )
            self._client.add_to_device_callback(
                self._events.emoji_verification, (KeyVerificationEvent,)
            )

            _LOGGER.debug("Starting sync_forever for %s", self._mx_id)
            # Create background task for sync_forever without awaiting it
            self.hass.async_create_background_task(
                self._client.sync_forever(
                    timeout=30_000,
                    loop_sleep_time=1_000,
                ),  # milliseconds.
                name=f"{self.__class__.__name__}: sync_forever for '{self._mx_id}'",
            )

            _LOGGER.debug("Matrix bot startup completed for %s", self._mx_id)

        self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, handle_startup)

    async def handle_send_message(self, service_data: dict) -> None:
        """Handle the send_message service."""
        await self._messages.handle_send_message(service_data)
