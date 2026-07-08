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

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowContext
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.translation import async_invalidate_translations
from homeassistant.loader import async_get_integration

from ._proto import sandbox_pb2 as pb
from .channel import ChannelClosedError, ChannelRemoteError
from .classifier import SandboxAssignment, classify
from .manager import SandboxManager
from .messages import (
    MSG_ENTRY_SETUP,
    MSG_ENTRY_UNLOAD,
    core_config_to_proto,
    entry_to_setup_proto,
)
from .proxy_flow import SandboxFlowProxy
from .sources import SandboxSourceError, async_resolve_integration_source

if TYPE_CHECKING:
    from . import SandboxData

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
        data: SandboxData | None = None,
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
        """Hand a sandboxed entry to the manager and run its setup remotely.

        Core owns the entry state: True marks the entry LOADED, a raised
        :class:`ConfigEntryError` marks it SETUP_ERROR with the message.
        """
        group = entry.sandbox
        if group is None:
            return None
        try:
            sandbox = await self._manager.ensure_started(group)
        except Exception as err:
            _LOGGER.exception(
                "Sandbox group %r failed to start for entry %s (%s)",
                group,
                entry.title,
                entry.domain,
            )
            raise ConfigEntryError("Sandbox failed to start") from err

        channel = sandbox.channel
        if channel is None:
            _LOGGER.error(
                "Sandbox %r has no live channel for entry %s (%s)",
                group,
                entry.title,
                entry.domain,
            )
            raise ConfigEntryError("Sandbox channel down")

        try:
            payload = await _entry_setup_payload(self._hass, entry)
        except SandboxSourceError as err:
            _LOGGER.error(
                "Cannot resolve integration source for entry %s (%s): %s",
                entry.title,
                entry.domain,
                err,
            )
            raise ConfigEntryError(str(err)) from err
        try:
            result = await channel.call(MSG_ENTRY_SETUP, payload)
        except ChannelClosedError as err:
            # The router runs *outside* ConfigEntry.async_setup, so the
            # SETUP_RETRY timer (async_call_later) that core wires there is
            # never armed for a sandbox entry — setting SETUP_RETRY here would
            # wedge the entry in a retry state that never retries (and a later
            # async_setup would raise OperationNotAllowed). Report SETUP_ERROR
            # honestly instead; the entry stays recoverable via a manual
            # reload. (Follow-up: a router-driven true retry — see
            # ARCHITECTURE.md §5.)
            raise ConfigEntryError(
                "Sandbox channel closed during setup; reload to retry"
            ) from err
        except ChannelRemoteError as err:
            raise ConfigEntryError(
                f"Sandbox raised {err.error_type or 'error'}: {err.error}"
            ) from err

        if not result.ok:
            reason = (
                result.reason if result.HasField("reason") else "sandbox refused setup"
            )
            raise ConfigEntryError(reason)

        return True

    async def async_unload_entry(self, entry: ConfigEntry) -> bool | None:
        """Push the unload back to the sandbox if the entry is sandboxed.

        Returns ``None`` for non-sandbox entries so the normal HA unload
        path runs. True means unloaded (core marks the entry NOT_LOADED);
        a raised :class:`ConfigEntryError` means a live sandbox refused the
        unload — the main-side proxies stay in place and core leaves the
        entry state untouched.
        """
        group = entry.sandbox
        if group is None:
            return None
        # A reload re-fetches the integration code (possibly at a new commit
        # ref) and re-runs setup, so its translation strings may have changed.
        # Drop the cached strings; the next frontend fetch re-pulls them.
        async_invalidate_translations(self._hass, {entry.domain})
        sandbox = self._manager.get(group)
        if sandbox is None or sandbox.channel is None:
            # The sandbox is down. Skip the remote entry_unload RPC (the
            # process is gone) but still tear down the main-side proxies +
            # EntityComponent platform registration, or a later re-setup
            # hits "has already been setup!".
            await self._async_unload_main_side(group, entry)
            return True
        try:
            result = await sandbox.channel.call(
                MSG_ENTRY_UNLOAD, pb.EntryUnload(entry_id=entry.entry_id)
            )
        except ChannelClosedError:
            # The channel died mid-unload — same as "down": the process is
            # effectively gone, so clean up the main side anyway rather than
            # leaking the platform.
            _LOGGER.warning(
                "Sandbox %r channel closed while unloading entry %s (%s);"
                " cleaning up main-side proxies",
                group,
                entry.title,
                entry.domain,
            )
            await self._async_unload_main_side(group, entry)
            return True
        except ChannelRemoteError as err:
            # A live sandbox refused the unload — the entry is still loaded
            # remotely, so leave the main-side proxies in place and report
            # the failure.
            _LOGGER.exception(
                "Sandbox %r failed to unload entry %s (%s)",
                group,
                entry.title,
                entry.domain,
            )
            raise ConfigEntryError(f"Sandbox refused to unload: {err.error}") from err
        if not result.ok:
            raise ConfigEntryError("Sandbox reported the unload failed")
        await self._async_unload_main_side(group, entry)
        return True

    async def _async_unload_main_side(self, group: str, entry: ConfigEntry) -> None:
        """Tear down the main-side proxies + platform slot for ``entry``.

        Shared by every :meth:`async_unload_entry` exit that should release
        main-side state: the remote ``entry_unload`` RPC is optional (it
        can't run when the sandbox is down) but the proxies and the
        ``EntityComponent`` platform registration must always be removed or a
        later re-setup trips the ``"has already been setup!"`` guard.
        """
        if self._data is None:
            return
        bridge = self._data.bridges.get(group)
        if bridge is not None:
            await bridge.async_unload_entry(entry)

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
    custom → a git source pinned to an exact sha), plus a ``core_config``
    snapshot of main's core configuration so the sandbox's private hass
    computes sun times / distances / unit conversions like main. May raise
    :class:`SandboxSourceError` if a custom integration has no source resolver.
    """
    msg = entry_to_setup_proto(entry)
    msg.integration_source.CopyFrom(
        await async_resolve_integration_source(hass, entry.domain)
    )
    msg.core_config.CopyFrom(core_config_to_proto(hass.config))
    return msg


__all__ = ["SandboxFlowRouter"]
