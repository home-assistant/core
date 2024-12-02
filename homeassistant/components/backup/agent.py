"""Backup agents for the Backup integration."""

from __future__ import annotations

import abc
import asyncio
from collections.abc import AsyncGenerator, Callable, Coroutine
from pathlib import Path
from typing import Any, Protocol

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .models import AgentBackup

type BackupAgentStream = aiohttp.StreamReader | asyncio.StreamReader


class BackupAgentError(HomeAssistantError):
    """Base class for backup agent errors."""


class BackupAgentUnreachableError(BackupAgentError):
    """Raised when the agent can't reach its API."""

    _message = "The backup agent is unreachable."


class BackupAgent(abc.ABC):
    """Backup agent interface."""

    name: str

    @abc.abstractmethod
    async def async_download_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> BackupAgentStream:
        """Download a backup file.

        :param backup_id: The ID of the backup that was returned in async_list_backups.
        :return: Either an aiohttp or asyncio StreamReader.
        """

    @abc.abstractmethod
    async def async_upload_backup(
        self,
        *,
        open_stream: Callable[[], Coroutine[Any, Any, AsyncGenerator[bytes]]],
        backup: AgentBackup,
        **kwargs: Any,
    ) -> None:
        """Upload a backup.

        :param open_stream: A function returning an async generator.
        :param backup: Metadata about the backup that should be uploaded.
        """

    @abc.abstractmethod
    async def async_delete_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> None:
        """Delete a backup file.

        :param backup_id: The ID of the backup that was returned in async_list_backups.
        """

    @abc.abstractmethod
    async def async_list_backups(self, **kwargs: Any) -> list[AgentBackup]:
        """List backups."""

    @abc.abstractmethod
    async def async_get_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> AgentBackup | None:
        """Return a backup."""


class LocalBackupAgent(BackupAgent):
    """Local backup agent."""

    @abc.abstractmethod
    def get_backup_path(self, backup_id: str) -> Path:
        """Return the local path to a backup.

        The method should return the path to the backup file with the specified id.
        """


class BackupAgentPlatformProtocol(Protocol):
    """Define the format of backup platforms which implement backup agents."""

    async def async_get_backup_agents(
        self,
        hass: HomeAssistant,
        **kwargs: Any,
    ) -> list[BackupAgent]:
        """Return a list of backup agents."""
