"""The Sandbox integration.

Manages config entries that should run in isolated sandbox processes.
Spawns sandbox processes and provides a websocket API for them to
register entities and push state back into HA Core.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
import logging
import sys
from typing import Any

from homeassistant.auth.models import RefreshToken, User
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.typing import ConfigType

from .const import DATA_SANDBOX, DOMAIN
from .entity import SandboxEntityManager
from . import websocket_api as sandbox_ws

_LOGGER = logging.getLogger(__name__)

type SandboxConfigEntry = ConfigEntry[SandboxEntryData]


@dataclass
class SandboxEntryConfig:
    """Configuration for a single entry that runs inside a sandbox."""

    entry_id: str
    domain: str
    title: str
    data: dict[str, Any]
    options: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        """Serialize to dict for the websocket API."""
        return {
            "entry_id": self.entry_id,
            "domain": self.domain,
            "title": self.title,
            "data": self.data,
            "options": self.options,
        }


@dataclass
class SandboxInstance:
    """A sandbox instance that runs one or more config entries."""

    sandbox_id: str
    entries: list[dict[str, Any]]
    user: User | None = None
    refresh_token: RefreshToken | None = None
    access_token: str | None = None
    process: asyncio.subprocess.Process | None = None
    managed_entity_ids: set[str] = field(default_factory=set)
    send_command: Callable[[dict[str, Any]], None] | None = None


@dataclass
class SandboxEntryData:
    """Runtime data for a sandbox config entry."""

    instance: SandboxInstance | None = None


@dataclass
class SandboxData:
    """Global sandbox data stored in hass.data."""

    sandboxes: dict[str, SandboxInstance] = field(default_factory=dict)
    token_to_sandbox: dict[str, str] = field(default_factory=dict)
    host_entry_ids: dict[str, str] = field(default_factory=dict)
    entity_managers: dict[str, Any] = field(default_factory=dict)

    def get_host_entry_id(self, sandbox_id: str) -> str | None:
        """Return the HA Core config entry ID that hosts this sandbox."""
        return self.host_entry_ids.get(sandbox_id)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Sandbox integration."""
    hass.data[DATA_SANDBOX] = SandboxData()
    sandbox_ws.async_setup(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: SandboxConfigEntry) -> bool:
    """Set up a sandbox from a config entry."""
    sandbox_data = hass.data[DATA_SANDBOX]

    sandbox_entries = entry.data.get("entries", [])
    if not sandbox_entries:
        _LOGGER.warning("Sandbox config entry %s has no entries to run", entry.entry_id)
        return True

    sandbox_id = entry.entry_id

    instance = SandboxInstance(
        sandbox_id=sandbox_id,
        entries=sandbox_entries,
    )

    user = await hass.auth.async_create_system_user(
        f"Sandbox {sandbox_id[:8]}",
        group_ids=["system-admin"],
    )
    refresh_token = await hass.auth.async_create_refresh_token(user)
    access_token = hass.auth.async_create_access_token(refresh_token)

    instance.user = user
    instance.refresh_token = refresh_token
    instance.access_token = access_token

    sandbox_data.sandboxes[sandbox_id] = instance
    sandbox_data.token_to_sandbox[refresh_token.id] = sandbox_id
    sandbox_data.host_entry_ids[sandbox_id] = entry.entry_id

    manager = SandboxEntityManager(hass, sandbox_id)
    sandbox_data.entity_managers[sandbox_id] = manager

    entry.runtime_data = SandboxEntryData(instance=instance)

    ws_url = _get_websocket_url(hass)
    if ws_url:
        instance.process = await _spawn_sandbox(
            hass, ws_url, access_token, sandbox_id
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: SandboxConfigEntry) -> bool:
    """Unload a sandbox config entry."""
    sandbox_data = hass.data[DATA_SANDBOX]
    sandbox_id = entry.entry_id
    instance = sandbox_data.sandboxes.pop(sandbox_id, None)

    if instance is None:
        return True

    if instance.process is not None:
        try:
            instance.process.terminate()
            await asyncio.wait_for(instance.process.wait(), timeout=10)
        except (ProcessLookupError, asyncio.TimeoutError):
            if instance.process.returncode is None:
                instance.process.kill()

    if instance.refresh_token is not None:
        sandbox_data.token_to_sandbox.pop(instance.refresh_token.id, None)
        hass.auth.async_remove_refresh_token(instance.refresh_token)

    if instance.user is not None:
        await hass.auth.async_remove_user(instance.user)

    sandbox_data.host_entry_ids.pop(sandbox_id, None)

    return True


@callback
def _get_websocket_url(hass: HomeAssistant) -> str | None:
    """Build the local websocket URL."""
    if not hasattr(hass, "http") or hass.http is None:
        return None
    port = hass.http.server_port or 8123
    return f"ws://127.0.0.1:{port}/api/websocket"


async def _spawn_sandbox(
    hass: HomeAssistant,
    ws_url: str,
    access_token: str,
    sandbox_id: str,
) -> asyncio.subprocess.Process:
    """Spawn a sandbox subprocess."""
    _LOGGER.info("Spawning sandbox process for %s", sandbox_id)
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "hass_client.sandbox",
        "--url",
        ws_url,
        "--token",
        access_token,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    async def _log_stream(
        stream: asyncio.StreamReader, level: int, prefix: str
    ) -> None:
        while True:
            line = await stream.readline()
            if not line:
                break
            _LOGGER.log(level, "[sandbox %s] %s", prefix, line.decode().rstrip())

    if process.stdout:
        hass.async_create_background_task(
            _log_stream(process.stdout, logging.INFO, sandbox_id[:8]),
            f"sandbox_stdout_{sandbox_id}",
        )
    if process.stderr:
        hass.async_create_background_task(
            _log_stream(process.stderr, logging.WARNING, sandbox_id[:8]),
            f"sandbox_stderr_{sandbox_id}",
        )

    return process
