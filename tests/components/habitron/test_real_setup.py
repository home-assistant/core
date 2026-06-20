"""End-to-end setup against a recorded real SmartHub.

Most config-entry tests stub ``SmartHub.async_setup`` so they never touch the
bus. This module instead replays an anonymised recording of a real 11-module
installation (the exact bytes the hub returned, captured via the library's
``scripts/capture_hub.py``) through a full config-entry setup. It exercises the
real build pipeline — ``async_build_system`` parsing, device registration,
area assignment and sensor-entity creation — against production-shaped data.
"""

from __future__ import annotations

import base64
from collections import deque
from typing import Any
from unittest.mock import AsyncMock, patch

from homeassistant.components.habitron.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import MOCK_HOST, MOCK_MAC

from tests.common import MockConfigEntry, async_load_json_object_fixture


class _ReplayClient:
    """A HabitronClient stand-in that replays recorded wire responses.

    Data reads are answered from per-method queues in recording order; control
    calls (connect, reinit, mirror, …) are no-ops. A method whose queue is
    exhausted repeats its last response so extra coordinator refreshes don't
    run the recording dry.
    """

    def __init__(self, recording: dict[str, Any]) -> None:
        self._queues: dict[str, deque[dict[str, Any]]] = {}
        for call in recording["calls"]:
            self._queues.setdefault(call["method"], deque()).append(call)
        self._last: dict[str, dict[str, Any]] = {}
        self._info = recording["smhub_info"]
        self.host = MOCK_HOST

    async def connect(self) -> None:
        """No-op: the replay has no live socket."""

    async def close(self) -> None:
        """No-op."""

    async def get_smhub_info(self) -> dict[str, Any]:
        """Return the recorded hub info dict."""
        return self._info

    async def get_smhub_update(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        """Skip host diagnostics in the replay (returns no data)."""
        return {}

    async def reinit_hub(self, *args: Any, **kwargs: Any) -> None:
        """No-op control call."""

    async def send_network_info(self, *args: Any, **kwargs: Any) -> None:
        """No-op control call."""

    async def start_mirror(self, *args: Any, **kwargs: Any) -> None:
        """No-op control call."""

    async def stop_mirror(self, *args: Any, **kwargs: Any) -> None:
        """No-op control call."""

    async def send_devregid(self, *args: Any, **kwargs: Any) -> None:
        """No-op control call."""

    def __getattr__(self, name: str) -> Any:
        """Replay a recorded data read for any non-control method."""

        async def _replay(*args: Any, **kwargs: Any) -> Any:
            queue = self._queues.get(name)
            if queue:
                entry = queue.popleft()
                self._last[name] = entry
            elif name in self._last:
                entry = self._last[name]
            else:
                raise AssertionError(f"no recorded response for {name!r}")
            payload = base64.b64decode(entry["bytes_b64"])
            if entry["kind"] == "bytes_crc":
                return payload, entry["crc"]
            return payload

        return _replay


async def test_real_recording_builds_devices_and_entities(
    hass: HomeAssistant,
    setup_homeassistant: None,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Replaying a real recording sets up the full device + entity model."""
    recording = await async_load_json_object_fixture(
        hass, "anon_recording.json", DOMAIN
    )
    # The anonymiser redacts the hub MAC to a non-hex placeholder; the network
    # handshake parses it as hex, so restore a structurally valid MAC.
    recording["smhub_info"]["hardware"]["network"]["lan mac"] = MOCK_MAC
    client = _ReplayClient(recording)
    mock_config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.habitron.communicate.HabitronClient",
            return_value=client,
        ),
        patch(
            "homeassistant.components.habitron.communicate.network.async_get_source_ip",
            new=AsyncMock(return_value="192.168.1.10"),
        ),
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Hub + router + the 11 recorded modules were registered as devices.
    dev_reg = dr.async_get(hass)
    devices = dr.async_entries_for_config_entry(dev_reg, mock_config_entry.entry_id)
    assert len(devices) >= recording["module_count"] + 2

    # The sensor platform created entities from the real module model.
    ent_reg = er.async_get(hass)
    entities = er.async_entries_for_config_entry(ent_reg, mock_config_entry.entry_id)
    assert any(entity.domain == "sensor" for entity in entities)
