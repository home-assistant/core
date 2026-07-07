"""Main-side :class:`ConfigEntryRouter` implementation.

Bridges :class:`homeassistant.config_entries.ConfigEntries` to the sandbox
manager:

* New flows for sandboxed integrations are diverted to a
  :class:`SandboxFlowProxy` that forwards each step over the sandbox's
  control :class:`Channel`.
* Existing config-entry setup is intercepted when ``entry.sandbox`` is
  set — the entry is handed to the sandbox manager and pushed into the
  sandbox runtime via ``sandbox/entry_setup``.

The router treats classifier output as the source of truth for which
sandbox a new entry should go into. Once an entry exists, the
``sandbox`` field stored on it wins (so a re-classification later
doesn't yank a running entry into a different sandbox).
"""

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowContext,
)
from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration

from ._proto import sandbox_pb2 as pb
from .channel import ChannelClosedError, ChannelRemoteError
from .classifier import SandboxAssignment, classify
from .manager import SandboxManager
from .messages import dict_to_struct
from .protocol import MSG_ENTRY_SETUP, MSG_ENTRY_UNLOAD
from .proxy_flow import SandboxFlowProxy
from .sources import SandboxSourceError, async_resolve_integration_source

if TYPE_CHECKING:
    from . import SandboxV2Data

_LOGGER = logging.getLogger(__name__)


class SandboxFlowRouter:
    """Route config flows and entry setup to sandbox processes.

    Structurally implements the :class:`ConfigEntryRouter` Protocol from
    ``homeassistant.config_entries``; declared as a plain class so the
    sandbox integration does not pull a runtime dependency on the
    protocol's import side-effects.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        manager: SandboxManager,
        *,
        data: SandboxV2Data | None = None,
    ) -> None:
        """Initialise the router with the active sandbox manager."""
        self._hass = hass
        self._manager = manager
        self._data = data

    async def async_create_flow(
        self,
        handler_key: str,
        *,
        context: ConfigFlowContext,
        data: Any,
    ) -> ConfigFlow | None:
        """Return a :class:`SandboxFlowProxy` if the integration is sandboxed."""
        assignment = await self._assignment_for_new_flow(handler_key)
        if assignment.is_main:
            return None
        assert assignment.group is not None
        return SandboxFlowProxy(
            sandbox_group=assignment.group,
            manager=self._manager,
            handler_key=handler_key,
        )

    async def async_setup_entry(self, entry: ConfigEntry) -> bool | None:
        """Hand a sandboxed entry to the manager and run its setup remotely."""
        group = entry.sandbox
        if group is None:
            return None
        try:
            sandbox = await self._manager.ensure_started(group)
        except Exception:
            _LOGGER.exception(
                "Sandbox group %r failed to start for entry %s (%s)",
                group,
                entry.title,
                entry.domain,
            )
            entry._async_set_state(  # noqa: SLF001
                self._hass, ConfigEntryState.SETUP_ERROR, "Sandbox failed to start"
            )
            return False

        channel = sandbox.channel
        if channel is None:
            _LOGGER.error(
                "Sandbox %r has no live channel for entry %s (%s)",
                group,
                entry.title,
                entry.domain,
            )
            entry._async_set_state(  # noqa: SLF001
                self._hass, ConfigEntryState.SETUP_ERROR, "Sandbox channel down"
            )
            return False

        try:
            payload = await _entry_setup_payload(self._hass, entry)
        except SandboxSourceError as err:
            _LOGGER.error(
                "Cannot resolve integration source for entry %s (%s): %s",
                entry.title,
                entry.domain,
                err,
            )
            entry._async_set_state(  # noqa: SLF001
                self._hass, ConfigEntryState.SETUP_ERROR, str(err)
            )
            return False
        try:
            result = await channel.call(MSG_ENTRY_SETUP, payload)
        except ChannelClosedError:
            entry._async_set_state(  # noqa: SLF001
                self._hass,
                ConfigEntryState.SETUP_RETRY,
                "Sandbox channel closed during setup",
            )
            return False
        except ChannelRemoteError as err:
            entry._async_set_state(  # noqa: SLF001
                self._hass,
                ConfigEntryState.SETUP_ERROR,
                f"Sandbox raised {err.error_type or 'error'}: {err.error}",
            )
            return False

        if not result.ok:
            reason = (
                result.reason if result.HasField("reason") else "sandbox refused setup"
            )
            entry._async_set_state(  # noqa: SLF001
                self._hass, ConfigEntryState.SETUP_ERROR, reason
            )
            return False

        entry._async_set_state(self._hass, ConfigEntryState.LOADED, None)  # noqa: SLF001
        return True

    async def async_unload_entry(self, entry: ConfigEntry) -> bool | None:
        """Push the unload back to the sandbox if the entry is sandboxed.

        Returns ``None`` for non-sandbox entries so the normal HA unload
        path runs.
        """
        group = entry.sandbox
        if group is None:
            return None
        sandbox = self._manager.get(group)
        if sandbox is None or sandbox.channel is None:
            return True
        try:
            result = await sandbox.channel.call(
                MSG_ENTRY_UNLOAD, pb.EntryUnload(entry_id=entry.entry_id)
            )
        except ChannelClosedError, ChannelRemoteError:
            _LOGGER.exception(
                "Sandbox %r failed to unload entry %s (%s)",
                group,
                entry.title,
                entry.domain,
            )
            return False
        if self._data is not None:
            bridge = self._data.bridges.get(group)
            if bridge is not None:
                await bridge.async_unload_entry(entry)
        return result.ok

    async def _assignment_for_new_flow(self, handler_key: str) -> SandboxAssignment:
        """Decide where a new flow for ``handler_key`` should run.

        First an existing entry's ``sandbox`` wins (so a flow for a
        domain that already has sandboxed entries goes to the same
        sandbox). Otherwise the classifier picks.
        """
        for existing in self._hass.config_entries.async_entries(handler_key):
            if (group := existing.sandbox) is not None:
                return SandboxAssignment(group=group)
        integration = await async_get_integration(self._hass, handler_key)
        return classify(integration)


async def _entry_setup_payload(
    hass: HomeAssistant, entry: ConfigEntry
) -> pb.EntrySetup:
    """Build the typed ``EntrySetup`` message for ``sandbox/entry_setup``.

    Surfaces the small subset of entry fields the integration's
    ``async_setup_entry`` reads, plus the ``integration_source`` descriptor
    telling a stateless sandbox where to fetch the code (built-in → no-op;
    custom → a git source pinned to an exact sha). May raise
    :class:`SandboxSourceError` if a custom integration has no source resolver.
    """
    msg = pb.EntrySetup(
        entry_id=entry.entry_id,
        domain=entry.domain,
        title=entry.title,
        data=dict_to_struct(dict(entry.data)),
        options=dict_to_struct(dict(entry.options)),
        source=entry.source,
        version=entry.version,
        minor_version=entry.minor_version,
    )
    if entry.unique_id is not None:
        msg.unique_id = entry.unique_id
    msg.integration_source.CopyFrom(
        await async_resolve_integration_source(hass, entry.domain)
    )
    return msg


__all__ = ["SandboxFlowRouter"]
