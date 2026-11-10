"""Common helpers for the Habitron tests."""

from __future__ import annotations

import base64
from collections import deque
from typing import Any

from habitron_client import HostDiagnostics

from .const import MOCK_HOST


class ReplayClient:
    """HabitronClient stand-in that replays a recorded SmartHub.

    Reads are answered in recording order and repeat the last answer once
    exhausted; control calls are no-ops.
    """

    def __init__(self, recording: dict[str, Any]) -> None:
        """Index the recorded calls by method."""
        self._queues: dict[str, deque[dict[str, Any]]] = {}
        for call in recording["calls"]:
            self._queues.setdefault(call["method"], deque()).append(call)
        self._last: dict[str, dict[str, Any]] = {}
        self._info = recording["smhub_info"]
        self.host = MOCK_HOST

    async def connect(self) -> None:
        """Do nothing, there is no socket."""

    async def close(self) -> None:
        """Do nothing, there is no socket."""

    async def get_smhub_info(self) -> dict[str, Any]:
        """Return the recorded hub info."""
        return self._info

    async def get_host_diagnostics(self, *args: Any, **kwargs: Any) -> HostDiagnostics:
        """Return neutral host readings."""
        return HostDiagnostics(
            cpu_frequency=0.0,
            cpu_load=0.0,
            cpu_temperature=0.0,
            memory_usage=0.0,
            disk_usage=0.0,
            log_level_console=0,
            log_level_file=0,
        )

    async def reinit_hub(self, *args: Any, **kwargs: Any) -> None:
        """Do nothing."""

    async def send_network_info(self, *args: Any, **kwargs: Any) -> None:
        """Do nothing."""

    async def start_mirror(self, *args: Any, **kwargs: Any) -> None:
        """Do nothing."""

    async def stop_mirror(self, *args: Any, **kwargs: Any) -> None:
        """Do nothing."""

    async def send_devregid(self, *args: Any, **kwargs: Any) -> None:
        """Do nothing."""

    def __getattr__(self, name: str) -> Any:
        """Replay a recorded read."""

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
