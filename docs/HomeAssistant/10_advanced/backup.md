---
title: "Backup"
---

There are two main purposes for an integration to implement a backup platform:

1. Add a backup agent that can upload backups to some local or remote location.
2. Pause or prepare integration operations before creating a backup and/or run some operation after a backup.

## Backup Agents

To add one or more backup agents, implement the two methods, `async_get_backup_agents` and `async_register_backup_agents_listener` in `backup.py`. Example:

```python
async def async_get_backup_agents(
    hass: HomeAssistant,
) -> list[BackupAgent]:
    """Return a list of backup agents."""
    if not hass.config_entries.async_loaded_entries(DOMAIN):
        LOGGER.debug("No config entry found or entry is not loaded")
        return []
    return [ExampleBackupAgent()]


@callback
def async_register_backup_agents_listener(
    hass: HomeAssistant,
    *,
    listener: Callable[[], None],
    **kwargs: Any,
) -> Callable[[], None]:
    """Register a listener to be called when agents are added or removed.

    :return: A function to unregister the listener.
    """
    hass.data.setdefault(DATA_BACKUP_AGENT_LISTENERS, []).append(listener)

    @callback
    def remove_listener() -> None:
        """Remove the listener."""
        hass.data[DATA_BACKUP_AGENT_LISTENERS].remove(listener)

    return remove_listener
```

The listener stored in `async_register_backup_agents_listener` should be called every time there is the need to reload backup agents, to remove stale agents and add new ones. This can be done by registering the listeners during `async_setup_entry`:

```python
async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up config entry."""
    # do things to set up your config entry

    # Notify backup listeners
    def notify_backup_listeners() -> None:
        for listener in hass.data.get(DATA_BACKUP_AGENT_LISTENERS, []):
            listener()
    entry.async_on_unload(entry.async_on_state_change(notify_backup_listeners))

    return True
```

A backup agent should implement the abstract interface of the `BackupAgent` base class as shown in this example:

```python
from homeassistant.components.backup import BackupAgent, BackupAgentError

from .const import DOMAIN


class ExampleBackupAgent(BackupAgent):
    """Backup agent interface."""

    domain = DOMAIN
    name = "Example Backup-Agent"
    unique_id = "example_stable_id"

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

    async def async_delete_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> None:
        """Delete a backup file.

        Raises BackupNotFound if the backup does not exist.

        :param backup_id: The ID of the backup that was returned in async_list_backups.
        """

    async def async_list_backups(self, **kwargs: Any) -> list[AgentBackup]:
        """List backups."""

    async def async_get_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> AgentBackup:
        """Return a backup.

        Raises BackupNotFound if the backup does not exist.
        """
```

Backup agents should raise a `BackupAgentError` (or a subclass of `BackupAgentError`) exception on error. Other exceptions are not expected to leave the backup agent.

## Pre- and post-operations

When Home Assistant is creating a backup, there might be a need to pause certain operations in the integration, or dumping data so it can properly be restored.

This is done by adding two functions (`async_pre_backup` and `async_post_backup`) to `backup.py`

### Adding support

The quickest way to add backup support to a new integration is by using our built-in scaffold template. From a Home Assistant dev environment, run `python3 -m script.scaffold backup` and follow the instructions.

If you prefer to go the manual route, create a new file in your integration folder called `backup.py` and implement the following method:

```python
from homeassistant.core import HomeAssistant


async def async_pre_backup(hass: HomeAssistant) -> None:
    """Perform operations before a backup starts."""

async def async_post_backup(hass: HomeAssistant) -> None:
    """Perform operations after a backup finishes."""
```
