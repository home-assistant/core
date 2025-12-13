"""Hegel media player platform."""

from __future__ import annotations

import asyncio
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
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import HegelConfigEntry
from .const import CONF_MODEL, DOMAIN, HEARTBEAT_TIMEOUT_MINUTES, MODEL_INPUTS
from .coordinator import HegelSlowPollCoordinator

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HegelConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Hegel media player from a config entry."""
    host = entry.data[CONF_HOST]
    name = entry.data.get(CONF_NAME, f"Hegel {host}")
    model = entry.data.get(CONF_MODEL)
    mac = entry.data.get("mac")
    unique_id = entry.data.get("unique_id")

    # map inputs (source_map)
    source_map: dict[int, str] = (
        dict(enumerate(MODEL_INPUTS[model], start=1)) if model in MODEL_INPUTS else {}
    )

    # Use the client from the config entry's runtime_data (already connected)
    client = entry.runtime_data

    # initial shared state container (shared between coordinator & entity)
    state: dict[str, Any] = {
        "power": False,
        "volume": 0.0,
        "mute": False,
        "input": None,
    }

    # Coordinator for slow background poll fallback
    coordinator = HegelSlowPollCoordinator(hass, client, state)
    # Fetch initial data (coordinator will attempt to connect and fetch)
    try:
        await coordinator.async_config_entry_first_refresh()
    except (HegelConnectionError, TimeoutError, OSError) as exc:
        _LOGGER.debug("Initial coordinator refresh failed: %s", exc)

    # Create entity
    media = HegelMediaPlayer(
        entry,
        name,
        client,
        source_map,
        state,
        mac,
        unique_id,
        coordinator,
    )

    async_add_entities([media])


class HegelMediaPlayer(CoordinatorEntity[HegelSlowPollCoordinator], MediaPlayerEntity):
    """Hegel amplifier entity using CoordinatorEntity for convenience."""

    _attr_should_poll = False

    def __init__(
        self,
        config_entry: HegelConfigEntry,
        name: str,
        client: HegelClient,
        source_map: dict[int, str],
        state: dict[str, Any],
        mac: str | None,
        unique_id: str | None,
        coordinator: HegelSlowPollCoordinator,
    ) -> None:
        """Initialize the Hegel media player entity."""
        CoordinatorEntity.__init__(self, coordinator)
        MediaPlayerEntity.__init__(self)

        self._entry = config_entry
        self._attr_name = name
        self._client = client
        self._source_map = source_map
        self._state = state
        self._mac = mac
        self._unique_id = unique_id

        # supported features
        self._attr_supported_features = (
            MediaPlayerEntityFeature.VOLUME_SET
            | MediaPlayerEntityFeature.VOLUME_MUTE
            | MediaPlayerEntityFeature.VOLUME_STEP
            | MediaPlayerEntityFeature.SELECT_SOURCE
            | MediaPlayerEntityFeature.TURN_ON
            | MediaPlayerEntityFeature.TURN_OFF
        )

        # Entity categorization for better organization
        self._attr_entity_category = None  # Primary device - no category needed
        self._attr_has_entity_name = True

        # Background tasks
        self._connected_watcher_task: asyncio.Task[None] | None = None
        self._push_task: asyncio.Task[None] | None = None

        # register push handler (schedule coroutine)
        # the client expects a synchronous callable; schedule a coroutine safely
        def push_handler(msg: str) -> None:
            self._push_task = asyncio.create_task(self._async_handle_push(msg))

        self._client.add_push_callback(push_handler)

        # start a watcher task to refresh state on reconnect
        self._connected_watcher_task = asyncio.create_task(self._connected_watcher())

    async def async_added_to_hass(self) -> None:
        """Handle entity added to Home Assistant."""
        # 1. Call parent (important for CoordinatorEntity)
        await super().async_added_to_hass()
        # 2. Schedule the heartbeat every 2 minutes while the reset timeout is 3 minutes
        self.async_on_remove(
            async_track_time_interval(
                self.hass,
                self._send_heartbeat,
                timedelta(minutes=HEARTBEAT_TIMEOUT_MINUTES - 1),
            )
        )
        # 3. Send the first heartbeat immediately
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

    @property
    def unique_id(self) -> str | None:
        """Return a unique ID for this entity."""
        # Prefer device-specific identifiers over IP-based ones
        if self._unique_id:
            return self._unique_id
        if self._mac:
            return f"hegel_{self._mac.replace(':', '')}"
        # Fallback to entry ID for consistency across reboots
        return f"hegel_{self._entry.entry_id}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for this entity."""
        unique_id = str(self.unique_id)

        info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            name=self._attr_name,
            manufacturer="Hegel",
            model=self._entry.data.get(CONF_MODEL),
        )
        if self._mac:
            info["connections"] = {(CONNECTION_NETWORK_MAC, self._mac)}
        return info

    async def _async_handle_push(self, msg: str) -> None:
        """Handle incoming push message from client (runs in event loop)."""
        try:
            update = parse_reply_message(msg)
            if update.has_changes():
                apply_state_changes(self._state, update, logger=_LOGGER, source="push")
                # notify HA
                self.async_write_ha_state()
        except (ValueError, KeyError, AttributeError):
            _LOGGER.exception("Failed to handle push message")

    async def _connected_watcher(self) -> None:
        """Watch the client's connected_event and refresh when it becomes set."""
        # Defensive: if client doesn't expose the event, skip watcher
        conn_event = getattr(self._client, "_connected_event", None)
        if not isinstance(conn_event, asyncio.Event):
            _LOGGER.debug("No connected event on client; skipping connected watcher")
            return

        _LOGGER.debug("Connected watcher started")
        try:
            while True:
                # wait for connection
                _LOGGER.debug("Watcher: waiting for connection event")
                await conn_event.wait()
                _LOGGER.debug("Hegel client connected — refreshing state")
                # immediately notify HA that we're available again
                self.async_write_ha_state()
                # do an immediate refresh (best-effort)
                try:
                    await self._refresh_state()
                except (HegelConnectionError, TimeoutError, OSError) as e:
                    _LOGGER.debug("Reconnect refresh failed: %s", e)

                # wait until disconnected before looping (to avoid spamming refresh)
                _LOGGER.debug("Watcher: waiting for disconnection")
                while conn_event.is_set():
                    await asyncio.sleep(0.5)
                _LOGGER.debug("Watcher: disconnected, notifying HA")
                # when disconnected, notify HA that we're unavailable
                self.async_write_ha_state()

        except asyncio.CancelledError:
            _LOGGER.debug("Connected watcher cancelled")
        except (HegelConnectionError, OSError):
            _LOGGER.exception("Connected watcher failed")

    async def _refresh_state(self) -> None:
        """Query the amplifier for the main values and update state dict."""
        try:
            for cmd in (
                COMMANDS["power_query"],
                COMMANDS["volume_query"],
                COMMANDS["mute_query"],
                COMMANDS["input_query"],
            ):
                try:
                    update = await self._client.send(
                        cmd, expect_reply=True, timeout=3.0
                    )
                    if update and update.has_changes():
                        apply_state_changes(
                            self._state, update, logger=_LOGGER, source="reconnect"
                        )
                except (HegelConnectionError, TimeoutError, OSError) as err:
                    _LOGGER.debug("Refresh command %s failed: %s", cmd, err)
            # update entity state
            self.async_write_ha_state()
        except (HegelConnectionError, TimeoutError, OSError) as err:
            _LOGGER.debug("Failed to refresh Hegel state: %s", err)

    @property
    def available(self) -> bool:
        """Return True if the client is connected."""
        conn_event = getattr(self._client, "_connected_event", None)
        is_available = bool(
            isinstance(conn_event, asyncio.Event) and conn_event.is_set()
        )
        _LOGGER.debug(
            "Availability check: %s (event set: %s)",
            is_available,
            conn_event.is_set() if conn_event else "N/A",
        )
        return is_available

    @property
    def state(self) -> MediaPlayerState | None:
        """Return the current state of the media player."""
        return MediaPlayerState.ON if self._state.get("power") else MediaPlayerState.OFF

    @property
    def volume_level(self) -> float | None:
        """Return the volume level."""
        return float(self._state.get("volume", 0.0))

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
            _LOGGER.warning("Failed to send power_on: %s", err)

    async def async_turn_off(self) -> None:
        """Turn off the media player."""
        try:
            await self._client.send(COMMANDS["power_off"], expect_reply=False)
        except (HegelConnectionError, TimeoutError, OSError) as err:
            _LOGGER.warning("Failed to send power_off: %s", err)

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        vol = max(0.0, min(volume, 1.0))
        amp_vol = int(round(vol * 100))
        try:
            await self._client.send(COMMANDS["volume_set"](amp_vol), expect_reply=False)
        except (HegelConnectionError, TimeoutError, OSError) as err:
            _LOGGER.warning("Failed to set volume: %s", err)

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute or unmute the volume."""
        try:
            await self._client.send(
                COMMANDS["mute_on" if mute else "mute_off"], expect_reply=False
            )
        except (HegelConnectionError, TimeoutError, OSError) as err:
            _LOGGER.warning("Failed to set mute: %s", err)

    async def async_volume_up(self) -> None:
        """Increase volume."""
        try:
            await self._client.send(COMMANDS["volume_up"], expect_reply=False)
        except (HegelConnectionError, TimeoutError, OSError) as err:
            _LOGGER.warning("Failed to increase volume: %s", err)

    async def async_volume_down(self) -> None:
        """Decrease volume."""
        try:
            await self._client.send(COMMANDS["volume_down"], expect_reply=False)
        except (HegelConnectionError, TimeoutError, OSError) as err:
            _LOGGER.warning("Failed to decrease volume: %s", err)

    async def async_select_source(self, source: str) -> None:
        """Select input source."""
        inv = {v: k for k, v in self._source_map.items()}
        idx = inv.get(source)
        if idx is not None:
            try:
                await self._client.send(COMMANDS["input_set"](idx), expect_reply=False)
            except (HegelConnectionError, TimeoutError, OSError) as err:
                _LOGGER.warning("Failed to select source %s: %s", source, err)

    async def async_will_remove_from_hass(self) -> None:
        """Handle entity removal from Home Assistant."""
        # Cancel background watcher and stop client
        if self._connected_watcher_task:
            self._connected_watcher_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._connected_watcher_task

