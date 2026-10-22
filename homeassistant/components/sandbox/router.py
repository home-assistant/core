"""Main-side :class:`ConfigEntryRouter` implementation."""

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowContext
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.translation import async_invalidate_translations
from homeassistant.loader import async_get_integration

from ._proto import sandbox_pb2 as pb
from .channel import ChannelClosedError, ChannelRemoteError
from .classifier import GROUP_BUILT_IN, GROUP_CUSTOM, MAIN, SandboxAssignment, classify
from .manager import SandboxManager
from .messages import (
    MSG_ENTRY_SETUP,
    MSG_ENTRY_UNLOAD,
    core_config_to_proto,
    entry_to_setup_proto,
)
from .proxy_flow import SandboxFlowProxy, SandboxSubentryFlowProxy
from .sources import SandboxSourceError, async_resolve_integration_source

if TYPE_CHECKING:
    from . import SandboxData

_LOGGER = logging.getLogger(__name__)


class SandboxFlowRouter:
    """Route config flows and entry setup to sandbox processes."""

    def __init__(
        self,
        hass: HomeAssistant,
        manager: SandboxManager,
        *,
        data: SandboxData | None = None,
        domains: frozenset[str] | None = None,
    ) -> None:
        """Initialise the router with the active sandbox manager."""
        self._hass = hass
        self._manager = manager
        self._data = data
        self._domains = domains

    async def async_setup_component(self, domain: str) -> bool | None:
        """Set up only config entries for selected domains, without running YAML setup."""
        if self._domains is None or domain not in self._domains:
            return None
        self._hass.config.components.add(domain)
        await asyncio.gather(
            *(
                entry.async_setup_locked(self._hass)
                for entry in self._hass.config_entries.async_entries(
                    domain, include_ignore=False, include_disabled=False
                )
            )
        )
        return True

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

    async def async_create_subentry_flow(
        self, entry: ConfigEntry, subentry_type: str
    ) -> SandboxSubentryFlowProxy | None:
        """Run subentry flows beside the integration's live Python objects."""
        if entry.sandbox is None:
            return None
        return SandboxSubentryFlowProxy(
            sandbox_group=entry.sandbox,
            manager=self._manager,
            handler_key=entry.domain,
            subentry_type=subentry_type,
        )

    async def async_setup_entry(self, entry: ConfigEntry) -> bool | None:
        """Hand a sandboxed entry to the manager and run its setup remotely."""
        if self._domains is not None:
            if entry.domain not in self._domains:
                return None
            # Own-domain proxy registration must not re-enter this entry's setup lock.
            self._hass.config.components.add(entry.domain)
        group = entry.sandbox
        if group is None and self._domains is None:
            return None
        try:
            if group is None:
                assignment = await self._assignment_for_new_flow(entry.domain)
                group = assignment.group
                assert group is not None
                # Placement is derived before setup; invalidate any cached storage view.
                object.__setattr__(entry, "sandbox", group)
                entry.clear_storage_cache()
            sandbox = await self._manager.ensure_started(group)
        except Exception as err:
            raise ConfigEntryError("Sandbox failed to start") from err

        channel = sandbox.channel
        if channel is None:
            raise ConfigEntryError("Sandbox channel down")

        try:
            payload = await _entry_setup_payload(self._hass, entry)
        except SandboxSourceError as err:
            raise ConfigEntryError(str(err)) from err
        if (
            self._data is not None
            and (bridge := self._data.bridges.get(group)) is not None
        ):
            bridge.entry_sync.track(entry)
        try:
            result = await channel.call(MSG_ENTRY_SETUP, payload)
        except ChannelClosedError as err:
            # The router has no retry timer; SETUP_ERROR keeps manual reload available.
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
        """Push the unload back to the sandbox if the entry is sandboxed."""
        group = entry.sandbox
        if group is None:
            return None
        # A reload re-fetches the integration code (possibly at a new commit
        # ref) and re-runs setup, so its translation strings may have changed.
        # Drop the cached strings; the next frontend fetch re-pulls them.
        async_invalidate_translations(self._hass, {entry.domain})
        sandbox = self._manager.get(group)
        if sandbox is None or sandbox.channel is None:
            # Release local platforms even when the worker cannot acknowledge unload.
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
            raise ConfigEntryError(f"Sandbox refused to unload: {err.error}") from err
        if not result.ok:
            raise ConfigEntryError("Sandbox reported the unload failed")
        await self._async_unload_main_side(group, entry)
        return True

    async def _async_unload_main_side(self, group: str, entry: ConfigEntry) -> None:
        """Tear down the main-side proxies + platform slot for ``entry``."""
        if self._data is None:
            return
        bridge = self._data.bridges.get(group)
        if bridge is not None:
            await bridge.async_unload_entry(entry)

    async def _assignment_for_new_flow(self, handler_key: str) -> SandboxAssignment:
        """Decide where a new flow for ``handler_key`` should run."""
        if self._domains is not None and handler_key not in self._domains:
            return MAIN
        for existing in self._hass.config_entries.async_entries(handler_key):
            if (group := existing.sandbox) is not None:
                return SandboxAssignment(group=group)
        integration = await async_get_integration(self._hass, handler_key)
        if self._domains is None:
            return classify(integration)
        return SandboxAssignment(
            group=GROUP_BUILT_IN if integration.is_built_in else GROUP_CUSTOM
        )


async def _entry_setup_payload(
    hass: HomeAssistant, entry: ConfigEntry
) -> pb.EntrySetup:
    """Build the typed ``EntrySetup`` message for ``sandbox/entry_setup``."""
    msg = entry_to_setup_proto(entry)
    msg.integration_source.CopyFrom(
        await async_resolve_integration_source(hass, entry.domain)
    )
    msg.core_config.CopyFrom(core_config_to_proto(hass.config))
    return msg


__all__ = ["SandboxFlowRouter"]
