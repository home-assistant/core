# media_player.py (revised)
from __future__ import annotations

import asyncio
import logging
import re
from datetime import timedelta
from typing import Any

from homeassistant.components.media_player import MediaPlayerEntity
from homeassistant.components.media_player.const import MediaPlayerEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
    CoordinatorEntity,
)

from .const import COMMANDS, MODEL_INPUTS, DOMAIN, SLOW_POLL_INTERVAL, CONF_MODEL
from .hegel_client import HegelClient

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
        hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
):
    """Set up the Hegel media player from a config entry."""
    host = entry.data[CONF_HOST]
    port = entry.data.get(CONF_PORT, 50001)
    name = entry.data.get(CONF_NAME, f"Hegel {host}")
    model = entry.data.get(CONF_MODEL)
    mac = entry.data.get("mac")
    unique_id = entry.data.get("unique_id")

    # map inputs (source_map)
    source_map: dict[int, str] = {}
    if model in MODEL_INPUTS:
        for idx, label in enumerate(MODEL_INPUTS[model], start=1):
            source_map[idx] = label

    # Create client and start its connection manager
    client = HegelClient(host, port)
    await client.start()

    # initial shared state container (shared between coordinator & entity)
    state: dict[str, Any] = {"power": False, "volume": 0.0, "mute": False, "input": None}

    # Coordinator for slow background poll fallback
    coordinator = HegelSlowPollCoordinator(hass, client, state)
    # Fetch initial data (coordinator will attempt to connect and fetch)
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as exc:
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

    # Store entities for unload if desired
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "client": client,
        "entities": [media],
        "coordinator": coordinator,
    }


def _update_state_from_reply(state: dict[str, Any], reply: str, source: str = "reply"):
    """Parse a single reply/push and update state dict."""
    if reply.startswith("-p."):
        state["power"] = reply.endswith(".1")
        _LOGGER.debug("[%s] Power parse: %s -> %s", source, reply, state["power"])
    elif reply.startswith("-v."):
        m = re.findall(r"-v\.(\d+)", reply)
        if m:
            level = int(m[-1])
            state["volume"] = max(0.0, min(1.0, level / 100.0))
            _LOGGER.debug("[%s] Volume parse: %s -> %s", source, reply, state["volume"])
    elif reply.startswith("-m."):
        # -m.1 means muted, -m.0 unmuted
        state["mute"] = "1" in reply and "0" not in reply
        _LOGGER.debug("[%s] Mute parse: %s -> %s", source, reply, state["mute"])
    elif reply.startswith("-i."):
        inp = None
        for n in range(1, 21):
            if f".{n}" in reply:
                inp = n
        state["input"] = inp
        _LOGGER.debug("[%s] Input parse: %s -> %s", source, reply, state["input"])
    elif reply.startswith("-r.") or reply.startswith("-reset"):
        _LOGGER.info("[%s] Reset/other message: %s", source, reply)
        state["reset"] = reply


class HegelSlowPollCoordinator(DataUpdateCoordinator):
    """Very slow fallback polling coordinator."""

    def __init__(self, hass: HomeAssistant, client: HegelClient, shared_state: dict):
        super().__init__(
            hass,
            _LOGGER,
            name="HegelSlowPoll",
            update_interval=timedelta(seconds=SLOW_POLL_INTERVAL),
        )
        self._client = client
        self._state = shared_state

    async def _async_update_data(self):
        """Periodically poll the amplifier to keep state in sync as a fallback."""
        try:
            await self._client.ensure_connected(timeout=5.0)
            responses = {}
            for key, cmd in {
                "power": COMMANDS["power_query"],
                "volume": COMMANDS["volume_query"],
                "mute": COMMANDS["mute_query"],
                "input": COMMANDS["input_query"],
            }.items():
                # expect a reply for each
                r = await self._client.send(cmd, expect_reply=True, timeout=3.0)
                if r:
                    responses[key] = r.strip()

            # translate into the shared dict
            for key, r in responses.items():
                _update_state_from_reply(self._state, r, source="poll")
            return self._state
        except Exception as err:
            _LOGGER.error("Slow poll failed: %s", err)
            raise UpdateFailed(str(err))


class HegelMediaPlayer(CoordinatorEntity, MediaPlayerEntity):
    """Hegel amplifier entity using CoordinatorEntity for convenience."""

    _attr_should_poll = False

    def __init__(
            self,
            config_entry: ConfigEntry,
            name: str,
            client: HegelClient,
            source_map: dict[int, str],
            state: dict[str, Any],
            mac: str | None,
            unique_id: str | None,
            coordinator: HegelSlowPollCoordinator,
    ) -> None:
        CoordinatorEntity.__init__(self, coordinator)
        MediaPlayerEntity.__init__(self)

        self._entry = config_entry
        self._attr_name = name
        self._client = client
        self._source_map = source_map
        self._state = state
        self._mac = mac
        self._unique_id = unique_id
        self._coordinator = coordinator

        # supported features
        self._attr_supported_features = (
                MediaPlayerEntityFeature.VOLUME_SET
                | MediaPlayerEntityFeature.VOLUME_MUTE
                | MediaPlayerEntityFeature.VOLUME_STEP
                | MediaPlayerEntityFeature.SELECT_SOURCE
                | MediaPlayerEntityFeature.TURN_ON
                | MediaPlayerEntityFeature.TURN_OFF
        )

        # Background tasks
        self._connected_watcher_task: asyncio.Task | None = None

        # register push handler (schedule coroutine)
        # the client expects a synchronous callable; schedule a coroutine safely
        self._client.add_push_callback(lambda m: asyncio.create_task(self._async_handle_push(m)))

        # start a watcher task to refresh state on reconnect
        self._connected_watcher_task = asyncio.create_task(self._connected_watcher())

    @property
    def unique_id(self) -> str | None:
        return self._unique_id or f"hegel-{self._entry.data.get(CONF_HOST)}"

    @property
    def device_info(self):
        info = {
            "identifiers": {(DOMAIN, self.unique_id)},
            "name": self._attr_name,
            "manufacturer": "Hegel",
            "model": self._entry.data.get(CONF_MODEL),
        }
        if self._mac:
            info["connections"] = {(CONNECTION_NETWORK_MAC, self._mac)}
        return info

    async def _async_handle_push(self, msg: str) -> None:
        """Handle incoming push message from client (runs in event loop)."""
        try:
            _update_state_from_reply(self._state, msg, source="push")
            # notify HA
            self.async_write_ha_state()
        except Exception as err:
            _LOGGER.exception("Failed to handle push message: %s", err)

    async def _connected_watcher(self) -> None:
        """Watch the client's connected_event and refresh when it becomes set."""
        # Defensive: if client doesn't expose the event, skip watcher
        conn_event = getattr(self._client, "_connected_event", None)
        if not isinstance(conn_event, asyncio.Event):
            _LOGGER.debug("No connected event on client; skipping connected watcher")
            return

        try:
            while True:
                # wait for connection
                await conn_event.wait()
                _LOGGER.debug("Hegel client connected — refreshing state")
                # do an immediate refresh (best-effort)
                try:
                    await self._refresh_state()
                except Exception as e:
                    _LOGGER.debug("Reconnect refresh failed: %s", e)

                # wait until disconnected before looping (to avoid spamming refresh)
                while conn_event.is_set():
                    await asyncio.sleep(0.5)

        except asyncio.CancelledError:
            pass
        except Exception as err:
            _LOGGER.exception("Connected watcher failed: %s", err)

    async def _refresh_state(self) -> None:
        """Query the amplifier for the main values and update state dict."""
        try:
            await self._client.ensure_connected(timeout=5.0)
            for key, cmd in {
                "power": COMMANDS["power_query"],
                "volume": COMMANDS["volume_query"],
                "mute": COMMANDS["mute_query"],
                "input": COMMANDS["input_query"],
            }.items():
                try:
                    r = await self._client.send(cmd, expect_reply=True, timeout=3.0)
                    if r:
                        _update_state_from_reply(self._state, r, source="reconnect")
                except Exception as err:
                    _LOGGER.debug("Refresh command %s failed: %s", cmd, err)
            # update entity state
            self.async_write_ha_state()
        except Exception as err:
            _LOGGER.debug("Failed to refresh Hegel state: %s", err)

    @property
    def available(self) -> bool:
        """Return True if the client is connected."""
        conn_event = getattr(self._client, "_connected_event", None)
        return bool(isinstance(conn_event, asyncio.Event) and conn_event.is_set())

    @property
    def state(self) -> str | None:
        return STATE_ON if self._state.get("power") else STATE_OFF

    @property
    def volume_level(self) -> float | None:
        return float(self._state.get("volume", 0.0))

    @property
    def is_volume_muted(self) -> bool | None:
        return bool(self._state.get("mute", False))

    @property
    def source(self) -> str | None:
        idx = self._state.get("input")
        return self._source_map.get(idx, f"Input {idx}") if idx else None

    @property
    def source_list(self) -> list[str] | None:
        return [self._source_map[k] for k in sorted(self._source_map.keys())] or None

    async def async_turn_on(self) -> None:
        try:
            await self._client.send(COMMANDS["power_on"], expect_reply=False)
        except Exception as err:
            _LOGGER.warning("Failed to send power_on: %s", err)
            return
        # rely on push or poll to update actual state
        self._state["power"] = True
        self.async_write_ha_state()

    async def async_turn_off(self) -> None:
        try:
            await self._client.send(COMMANDS["power_off"], expect_reply=False)
        except Exception as err:
            _LOGGER.warning("Failed to send power_off: %s", err)
            return
        self._state["power"] = False
        self.async_write_ha_state()

    async def async_set_volume_level(self, volume: float) -> None:
        vol = max(0.0, min(volume, 1.0))
        amp_vol = int(round(vol * 100))
        try:
            await self._client.send(COMMANDS["volume_set"](amp_vol), expect_reply=False)
        except Exception as err:
            _LOGGER.warning("Failed to set volume: %s", err)
            return
        # optimistic update — amplifier will send push reply soon
        self._state["volume"] = vol
        self.async_write_ha_state()

    async def async_mute_volume(self, mute: bool) -> None:
        try:
            await self._client.send(COMMANDS["mute_on" if mute else "mute_off"], expect_reply=False)
        except Exception as err:
            _LOGGER.warning("Failed to set mute: %s", err)
            return
        self._state["mute"] = mute
        self.async_write_ha_state()

    async def async_volume_up(self) -> None:
        try:
            await self._client.send(COMMANDS["volume_up"], expect_reply=False)
        except Exception as err:
            _LOGGER.warning("Failed to increase volume: %s", err)

    async def async_volume_down(self) -> None:
        try:
            await self._client.send(COMMANDS["volume_down"], expect_reply=False)
        except Exception as err:
            _LOGGER.warning("Failed to decrease volume: %s", err)

    async def async_select_source(self, source: str) -> None:
        inv = {v: k for k, v in self._source_map.items()}
        idx = inv.get(source)
        if idx is not None:
            try:
                await self._client.send(COMMANDS["input_set"](idx), expect_reply=False)
            except Exception as err:
                _LOGGER.warning("Failed to select source %s: %s", source, err)
                return
            self._state["input"] = idx
            self.async_write_ha_state()

    async def async_will_remove_from_hass(self):
        # Cancel background watcher and stop client
        if self._connected_watcher_task:
            self._connected_watcher_task.cancel()
            try:
                await self._connected_watcher_task
            except asyncio.CancelledError:
                pass

        # stop client manager
        try:
            await self._client.stop()
        except Exception as err:
            _LOGGER.debug("Error while stopping Hegel client: %s", err)
