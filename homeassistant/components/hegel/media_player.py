"""Hegel media player platform."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import contextlib
from datetime import timedelta
import logging
from typing import Any

from hegel_ip_client import (
    COMMANDS,
    HegelClient,
    apply_state_changes,
    parse_reply_message,
)
from hegel_ip_client.exceptions import HegelConnectionError

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval

from . import HegelConfigEntry
from .const import CONF_MODEL, DOMAIN, HEARTBEAT_TIMEOUT_MINUTES, MODEL_INPUTS

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HegelConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Hegel media player from a config entry."""
    model = entry.data[CONF_MODEL]
    unique_id = entry.unique_id or entry.entry_id

    # map inputs (source_map)
    source_map: dict[int, str] = (
        dict(enumerate(MODEL_INPUTS[model], start=1)) if model in MODEL_INPUTS else {}
    )

    # Use the client from the config entry's runtime_data (already connected)
    client = entry.runtime_data

    # Create entity
    media = HegelMediaPlayer(
        entry,
        client,
        source_map,
        unique_id,
    )

    async_add_entities([media])


class HegelMediaPlayer(MediaPlayerEntity):
    """Hegel amplifier entity."""

    _attr_should_poll = False
    _attr_name = None
    _attr_has_entity_name = True
    _attr_supported_features = (
        MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.SELECT_SOURCE
        | MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
    )

    def __init__(
        self,
        config_entry: HegelConfigEntry,
        client: HegelClient,
        source_map: dict[int, str],
        unique_id: str,
    ) -> None:
        """Initialize the Hegel media player entity."""
        self._entry = config_entry
        self._client = client
        self._source_map = source_map

        # Set unique_id from config entry
        self._attr_unique_id = unique_id

        # Set device info
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            name=config_entry.title,
            manufacturer="Hegel",
            model=config_entry.data[CONF_MODEL],
        )

        # State will be populated by async_update on first connection
        self._state: dict[str, Any] = {}

        # Background tasks
        self._connected_watcher_task: asyncio.Task[None] | None = None
        self._push_task: asyncio.Task[None] | None = None
        self._push_handler: Callable[[str], None] | None = None

    async def async_added_to_hass(self) -> None:
        """Handle entity added to Home Assistant."""
        await super().async_added_to_hass()
        _LOGGER.debug("Hegel media player added to hass: %s", self.entity_id)

        # Register push handler for real-time updates from the amplifier
        # The client expects a synchronous callable; schedule a coroutine safely
        def push_handler(msg: str) -> None:
            self._push_task = self.hass.async_create_task(self._async_handle_push(msg))

        self._push_handler = push_handler
        self._client.add_push_callback(push_handler)

        # Register cleanup for push handler using async_on_remove
        def cleanup_push_handler() -> None:
            if self._push_handler:
                self._client.remove_push_callback(self._push_handler)
                _LOGGER.debug("Push callback removed")
            self._push_handler = None

        self.async_on_remove(cleanup_push_handler)

        # Perform initial state fetch if already connected
        # The watcher handles reconnections, but we need to fetch state on first setup
        if self._client.is_connected():
            _LOGGER.debug("Client already connected, performing initial state fetch")
            await self.async_update()

        # Start a watcher task
        # Use config_entry.async_create_background_task for automatic cleanup on unload
        self._connected_watcher_task = self._entry.async_create_background_task(
            self.hass,
            self._connected_watcher(),
            name=f"hegel_{self.entity_id}_connected_watcher",
        )
        # Note: No need for async_on_remove - entry.async_create_background_task
        # automatically cancels the task when the config entry is unloaded

        # Schedule the heartbeat every 2 minutes while the reset timeout is 3 minutes
        self.async_on_remove(
            async_track_time_interval(
                self.hass,
                self._send_heartbeat,
                timedelta(minutes=HEARTBEAT_TIMEOUT_MINUTES - 1),
            )
        )
        # Send the first heartbeat immediately
        self.hass.async_create_task(self._send_heartbeat())

    async def _send_heartbeat(self, now=None) -> None:
        if not self.available:
            return
        try:
            await self._client.send(
                f"-r.{HEARTBEAT_TIMEOUT_MINUTES}", expect_reply=False
            )
        except (HegelConnectionError, TimeoutError, OSError) as err:
            _LOGGER.debug("Heartbeat failed: %s", err)

    async def _async_handle_push(self, msg: str) -> None:
        """Handle incoming push message from client (runs in event loop)."""
        try:
            update = parse_reply_message(msg)
            if update.has_changes():
                apply_state_changes(self._state, update, logger=_LOGGER, source="push")
                # notify HA
                self.async_write_ha_state()
        except ValueError, KeyError, AttributeError:
            _LOGGER.exception("Failed to handle push message")

    async def _connected_watcher(self) -> None:
        """Watch the client's connection events and update state accordingly."""
        conn_event = self._client.connected_event
        disconn_event = self._client.disconnected_event
        _LOGGER.debug("Connected watcher started")

        try:
            while True:
                # Wait for connection
                _LOGGER.debug("Watcher: waiting for connection")
                await conn_event.wait()
                _LOGGER.debug("Watcher: connected, refreshing state")

                # Immediately notify HA that we're available again
                self.async_write_ha_state()

                # Schedule a state refresh through HA
                self.async_schedule_update_ha_state(force_refresh=True)

                # Wait for disconnection using event (no polling!)
                _LOGGER.debug("Watcher: waiting for disconnection")
                await disconn_event.wait()
                _LOGGER.debug("Watcher: disconnected")

                # Notify HA that we're unavailable
                self.async_write_ha_state()

        except asyncio.CancelledError:
            _LOGGER.debug("Connected watcher cancelled")
        except (HegelConnectionError, OSError) as err:
            _LOGGER.warning("Connected watcher failed: %s", err)

    async def async_will_remove_from_hass(self) -> None:
        """Handle entity removal from Home Assistant.

        Note: Push callback cleanup is handled by async_on_remove.
        _connected_watcher_task cleanup is handled automatically by
        entry.async_create_background_task when the config entry is unloaded.
        """
        await super().async_will_remove_from_hass()

        # Cancel push task if running (short-lived task, defensive cleanup)
        if self._push_task and not self._push_task.done():
            self._push_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._push_task

    async def async_update(self) -> None:
        """Query the amplifier for the main values and update state dict."""
        for cmd in (
            COMMANDS["power_query"],
            COMMANDS["volume_query"],
            COMMANDS["mute_query"],
            COMMANDS["input_query"],
        ):
            try:
                update = await self._client.send(cmd, expect_reply=True, timeout=3.0)
                if update and update.has_changes():
                    apply_state_changes(
                        self._state, update, logger=_LOGGER, source="update"
                    )
            except (HegelConnectionError, TimeoutError, OSError) as err:
                _LOGGER.debug("Refresh command %s failed: %s", cmd, err)
        # update entity state
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return True if the client is connected."""
        return self._client.is_connected()

    @property
    def state(self) -> MediaPlayerState | None:
        """Return the current state of the media player."""
        power = self._state.get("power")
        if power is None:
            return None
        return MediaPlayerState.ON if power else MediaPlayerState.OFF

    @property
    def volume_level(self) -> float | None:
        """Return the volume level."""
        volume = self._state.get("volume")
        if volume is None:
            return None
        return float(volume)

    @property
    def is_volume_muted(self) -> bool | None:
        """Return whether volume is muted."""
        return bool(self._state.get("mute", False))

    @property
    def source(self) -> str | None:
        """Return the current input source."""
        idx = self._state.get("input")
        return self._source_map.get(idx, f"Input {idx}") if idx else None

    @property
    def source_list(self) -> list[str] | None:
        """Return the list of available input sources."""
        return [self._source_map[k] for k in sorted(self._source_map.keys())] or None

    async def async_turn_on(self) -> None:
        """Turn on the media player."""
        try:
            await self._client.send(COMMANDS["power_on"], expect_reply=False)
        except (HegelConnectionError, TimeoutError, OSError) as err:
            raise HomeAssistantError(f"Failed to turn on: {err}") from err

    async def async_turn_off(self) -> None:
        """Turn off the media player."""
        try:
            await self._client.send(COMMANDS["power_off"], expect_reply=False)
        except (HegelConnectionError, TimeoutError, OSError) as err:
            raise HomeAssistantError(f"Failed to turn off: {err}") from err

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        vol = max(0.0, min(volume, 1.0))
        amp_vol = int(round(vol * 100))
        try:
            await self._client.send(COMMANDS["volume_set"](amp_vol), expect_reply=False)
        except (HegelConnectionError, TimeoutError, OSError) as err:
            raise HomeAssistantError(f"Failed to set volume: {err}") from err

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute or unmute the volume."""
        try:
            await self._client.send(
                COMMANDS["mute_on" if mute else "mute_off"], expect_reply=False
            )
        except (HegelConnectionError, TimeoutError, OSError) as err:
            raise HomeAssistantError(f"Failed to set mute: {err}") from err

    async def async_volume_up(self) -> None:
        """Increase volume."""
        try:
            await self._client.send(COMMANDS["volume_up"], expect_reply=False)
        except (HegelConnectionError, TimeoutError, OSError) as err:
            raise HomeAssistantError(f"Failed to increase volume: {err}") from err

    async def async_volume_down(self) -> None:
        """Decrease volume."""
        try:
            await self._client.send(COMMANDS["volume_down"], expect_reply=False)
        except (HegelConnectionError, TimeoutError, OSError) as err:
            raise HomeAssistantError(f"Failed to decrease volume: {err}") from err

    async def async_select_source(self, source: str) -> None:
        """Select input source."""
        inv = {v: k for k, v in self._source_map.items()}
        idx = inv.get(source)
        if idx is None:
            raise ServiceValidationError(f"Unknown source: {source}")
        try:
            await self._client.send(COMMANDS["input_set"](idx), expect_reply=False)
        except (HegelConnectionError, TimeoutError, OSError) as err:
            raise HomeAssistantError(
                f"Failed to select source {source}: {err}"
            ) from err
