"""Backup agents for the Backup integration."""

from __future__ import annotations

import abc
from collections.abc import AsyncIterator, Callable, Coroutine
from pathlib import Path
from typing import Any, Protocol

from propcache.api import cached_property

from homeassistant.core import HomeAssistant, callback

from .models import AgentBackup, BackupAgentError


class BackupAgentUnreachableError(BackupAgentError):
    """Raised when the agent can't reach its API."""

    error_code = "backup_agent_unreachable"
    _message = "The backup agent is unreachable."


class BackupAgent(abc.ABC):
    """Backup agent interface."""

    domain: str
    name: str
    unique_id: str

    @cached_property
    def agent_id(self) -> str:
        """Return the agent_id."""
        return f"{self.domain}.{self.unique_id}"

    @abc.abstractmethod
    async def async_download_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> AsyncIterator[bytes]:
        """Download a backup file.

        Raises BackupNotFound if the backup does not exist.

        :param backup_id: The ID of the backup that was returned in async_list_backups.
        :return: An async iterator that yields bytes.
        """

    @abc.abstractmethod
    async def async_upload_backup(
        self,
        *,
        open_stream: Callable[[], Coroutine[Any, Any, AsyncIterator[bytes]]],
        backup: AgentBackup,
        **kwargs: Any,
    ) -> None:
        """Upload a backup.

        :param open_stream: A function returning an async iterator that yields bytes.
        :param backup: Metadata about the backup that should be uploaded.
        """

    @abc.abstractmethod
    async def async_delete_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> None:
        """Delete a backup file.

        Raises BackupNotFound if the backup does not exist.

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
    ) -> AgentBackup:
        """Return a backup.

        Raises BackupNotFound if the backup does not exist.
        """


class LocalBackupAgent(BackupAgent):
    """Local backup agent."""

    @abc.abstractmethod
    def get_backup_path(self, backup_id: str) -> Path:
        """Return the local path to an existing backup.

        The method should return the path to the backup file with the specified id.
        Raises BackupAgentError if the backup does not exist.
        """

    @abc.abstractmethod
    def get_new_backup_path(self, backup: AgentBackup) -> Path:
        """Return the local path to a new backup."""


class BackupAgentPlatformProtocol(Protocol):
    """Define the format of backup platforms which implement backup agents."""

    async def async_get_backup_agents(
        self,
        hass: HomeAssistant,
        **kwargs: Any,
    ) -> list[BackupAgent]:
        """Return a list of backup agents."""

    @callback
    def async_register_backup_agents_listener(
        self,
        hass: HomeAssistant,
        *,
        listener: Callable[[], None],
        **kwargs: Any,
    ) -> Callable[[], None]:
        """Register a listener to be called when agents are added or removed.

        :return: A function to unregister the listener.
        """
