# media_player.py
from __future__ import annotations

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
)

from .const import COMMANDS, MODEL_INPUTS, DOMAIN, SLOW_POLL_INTERVAL, CONF_MODEL
from .hegel_client import HegelClient

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    host = entry.data[CONF_HOST]
    port = entry.data.get(CONF_PORT, 50001)
    name = entry.data.get(CONF_NAME, f"Hegel {host}")
    model = entry.data.get(CONF_MODEL)
    mac = entry.data.get("mac")
    unique_id = entry.data.get("unique_id")

    # map inputs
    source_map: dict[int, str] = {}
    if model in MODEL_INPUTS:
        for idx, label in enumerate(MODEL_INPUTS[model], start=1):
            source_map[idx] = label

    client = HegelClient(host, port)
    # start manager (connect & reconnect) immediately
    await client.start()

    # initial state container
    state = {"power": False, "volume": 0.0, "mute": False, "input": None}

    # Perform initial fetch (use send expecting replies). If fails, we rely on push once it connects.
    try:
        # ensure connected (wait a little)
        await client.ensure_connected(timeout=5.0)
        for key, cmd in {
            "power": COMMANDS["power_query"],
            "volume": COMMANDS["volume_query"],
            "mute": COMMANDS["mute_query"],
            "input": COMMANDS["input_query"],
        }.items():
            resp = await client.send(cmd, expect_reply=True, timeout=2.0)
            if resp:
                _update_state_from_reply(state, resp, source="init")
    except Exception as e:
        _LOGGER.debug("Initial fetch failed or timed out; continuing and waiting for push updates: %s", e)

    # coordinator for slow background poll fallback
    coordinator = HegelSlowPollCoordinator(hass, client)
    await coordinator.async_config_entry_first_refresh()

    media = HegelMediaPlayer(entry, name, client, source_map, state, mac, unique_id, coordinator)
    async_add_entities([media])


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
        # optional reset handling
        _LOGGER.info("[%s] Reset/other message: %s", source, reply)
        state["reset"] = reply


class HegelSlowPollCoordinator(DataUpdateCoordinator):
    """Very slow fallback polling coordinator (e.g. 1 hour)."""

    def __init__(self, hass: HomeAssistant, client: HegelClient):
        super().__init__(hass, _LOGGER, name="HegelSlowPoll", update_interval=timedelta(seconds=SLOW_POLL_INTERVAL))
        self._client = client
        self.state: dict[str, Any] = {}

    async def _async_update_data(self):
        try:
            await self._client.ensure_connected(timeout=5.0)
            responses = {}
            for key, cmd in {
                "power": COMMANDS["power_query"],
                "volume": COMMANDS["volume_query"],
                "mute": COMMANDS["mute_query"],
                "input": COMMANDS["input_query"],
            }.items():
                r = await self._client.send(cmd, expect_reply=True, timeout=2.0)
                if r:
                    responses[key] = r.strip()

            # translate into one dict (reuse parsing function)
            for key, r in responses.items():
                _update_state_from_reply(self.state, r, source="poll")
            return self.state
        except Exception as err:
            _LOGGER.error("Slow poll failed: %s", err)
            raise UpdateFailed(str(err))


class HegelMediaPlayer(MediaPlayerEntity):
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
        self._entry = config_entry
        self._attr_name = name
        self._client = client
        self._source_map = source_map
        self._state = state
        self._mac = mac
        self._unique_id = unique_id
        self._coordinator = coordinator

        self._attr_supported_features = (
            MediaPlayerEntityFeature.VOLUME_SET
            | MediaPlayerEntityFeature.VOLUME_MUTE
            | MediaPlayerEntityFeature.VOLUME_STEP
            | MediaPlayerEntityFeature.SELECT_SOURCE
            | MediaPlayerEntityFeature.TURN_ON
            | MediaPlayerEntityFeature.TURN_OFF
        )

        # register push handler
        self._client.add_push_callback(self._handle_push)

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

    def _handle_push(self, msg: str) -> None:
        _update_state_from_reply(self._state, msg, source="push")
        # notify HA
        try:
            self.async_write_ha_state()
        except Exception:
            # entity may not be added yet — ignore
            pass

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
        await self._client.send(COMMANDS["power_on"], expect_reply=False)
        self._state["power"] = True
        self.async_write_ha_state()

    async def async_turn_off(self) -> None:
        await self._client.send(COMMANDS["power_off"], expect_reply=False)
        self._state["power"] = False
        self.async_write_ha_state()

    async def async_set_volume_level(self, volume: float) -> None:
        vol = max(0.0, min(volume, 1.0))
        amp_vol = int(round(volume * 100)) 
        await self._client.send(COMMANDS["volume_set"](amp_vol), expect_reply=False)
        self._state["volume"] = vol
        self.async_write_ha_state()

    async def async_mute_volume(self, mute: bool) -> None:
        await self._client.send(COMMANDS["mute_on" if mute else "mute_off"], expect_reply=False)
        self._state["mute"] = mute
        self.async_write_ha_state()

    async def async_volume_up(self) -> None:
        if self._state["volume"] is not None:
            new_vol = min(1.0, self._state["volume"] + 0.01)
            self._state["volume"] = new_vol
            self.async_write_ha_state()
        await self._client.send(COMMANDS["volume_up"], expect_reply=False)

    async def async_volume_down(self) -> None:
        if self._state["volume"] is not None:
            new_vol = max(0.0, self._state["volume"] - 0.01)
            self._state["volume"] = new_vol
            self.async_write_ha_state()
        await self._client.send(COMMANDS["volume_down"], expect_reply=False)

    async def async_select_source(self, source: str) -> None:
        inv = {v: k for k, v in self._source_map.items()}
        idx = inv.get(source)
        if idx is not None:
            await self._client.send(COMMANDS["input_set"](idx), expect_reply=False)
            self._state["input"] = idx
            self.async_write_ha_state()

    async def async_will_remove_from_hass(self):
        await self._client.stop()
