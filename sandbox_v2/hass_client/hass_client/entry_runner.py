"""Sandbox-side entry runner — loads integrations + drives ``async_setup_entry``.

The manager pushes a serialised :class:`ConfigEntry` via
``sandbox_v2/entry_setup`` (see :mod:`hass_client.protocol`). The runner
rebuilds the entry on the sandbox's private :class:`HomeAssistant`,
calls ``hass.config_entries.async_setup`` to load the owning integration,
and reports back. Main holds the canonical entry; the sandbox copy is
ephemeral state used by the integration's lifecycle hooks.
"""

import logging
from types import MappingProxyType

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant

from ._proto import sandbox_v2_pb2 as pb
from .approved_domains import ApprovedDomains
from .channel import Channel
from .messages import dict_to_struct, struct_to_dict
from .protocol import MSG_CALL_SERVICE, MSG_ENTRY_SETUP, MSG_ENTRY_UNLOAD
from .sources import FetchPrimitive, SandboxSourceError, async_ensure_integration_source

_LOGGER = logging.getLogger(__name__)


class EntryRunner:
    """Load integrations on demand and run config entries inside the sandbox."""

    def __init__(
        self,
        hass: HomeAssistant,
        approved: ApprovedDomains | None = None,
        *,
        fetch: FetchPrimitive | None = None,
    ) -> None:
        """Initialise with the sandbox-private HA instance.

        ``approved`` is shared with the service + event mirrors so an
        entry's domain becomes approved as soon as setup completes.
        ``fetch`` overrides the integration-source download primitive (tests
        inject a local stub); ``None`` uses the real codeload tarball fetch.
        """
        self.hass = hass
        self.approved = approved if approved is not None else ApprovedDomains()
        self._fetch = fetch

    def register(self, channel: Channel) -> None:
        """Wire the ``sandbox_v2/entry_*`` + ``call_service`` handlers."""
        channel.register(MSG_ENTRY_SETUP, self._handle_entry_setup)
        channel.register(MSG_ENTRY_UNLOAD, self._handle_entry_unload)
        channel.register(MSG_CALL_SERVICE, self._handle_call_service)

    async def _handle_entry_setup(self, msg: pb.EntrySetup) -> pb.EntrySetupResult:
        """Build a :class:`ConfigEntry`, register it, and call async_setup."""
        try:
            entry = _entry_from_proto(msg)
        except (KeyError, TypeError) as err:
            return pb.EntrySetupResult(ok=False, reason=f"bad payload: {err}")

        # Fetch the integration code before setup so a stateless sandbox can
        # load custom (HACS) integrations whose code isn't bundled. Built-in
        # sources are a no-op.
        try:
            await async_ensure_integration_source(
                self.hass.config.config_dir,
                msg.integration_source,
                fetch=self._fetch,
            )
        except SandboxSourceError as err:
            _LOGGER.error(
                "sandbox entry_setup: source fetch failed for %s (%s): %s",
                entry.title,
                entry.domain,
                err,
            )
            return pb.EntrySetupResult(ok=False, reason=f"source fetch failed: {err}")

        config_entries = self.hass.config_entries
        if config_entries.async_get_entry(entry.entry_id) is not None:
            return pb.EntrySetupResult(ok=False, reason="entry already loaded")

        # ConfigEntries doesn't expose a "add without persist" hook; the
        # sandbox's instance has no Store backing, so we drop the entry
        # straight into the internal map. `async_setup` then finds it via
        # `async_get_known_entry`.
        config_entries._entries[entry.entry_id] = entry  # noqa: SLF001
        try:
            ok = await config_entries.async_setup(entry.entry_id)
        except Exception as err:
            _LOGGER.exception(
                "sandbox entry_setup raised for %s (%s)", entry.title, entry.domain
            )
            return pb.EntrySetupResult(
                ok=False, reason=str(err) or err.__class__.__name__
            )
        if not ok:
            return pb.EntrySetupResult(
                ok=False, reason=entry.reason or f"async_setup returned {ok!r}"
            )
        self.approved.add(entry.domain)
        return pb.EntrySetupResult(ok=True)

    async def _handle_entry_unload(self, msg: pb.EntryUnload) -> pb.EntryUnloadResult:
        """Unload an entry by id and drop it from the sandbox's store."""
        entry_id = msg.entry_id
        config_entries = self.hass.config_entries
        entry = config_entries.async_get_entry(entry_id)
        if entry is None:
            return pb.EntryUnloadResult(ok=True)
        try:
            unloaded = await config_entries.async_unload(entry_id)
        except Exception:
            _LOGGER.exception("sandbox entry_unload raised for %s", entry_id)
            return pb.EntryUnloadResult(ok=False)
        config_entries._entries.pop(entry_id, None)  # noqa: SLF001
        # Drop one approval refcount; another loaded entry of the same
        # domain keeps it approved.
        self.approved.remove(entry.domain)
        return pb.EntryUnloadResult(ok=bool(unloaded))

    async def _handle_call_service(self, msg: pb.CallService) -> pb.CallServiceResult:
        """Dispatch a main→sandbox service call through HA's normal path.

        Service-handler errors propagate as raised exceptions so the
        :class:`Channel`'s error frame carries the type name (e.g.
        ``Invalid``). Main maps those back to ``TypeError`` /
        ``HomeAssistantError`` in :mod:`bridge`'s exception translator.
        """
        target = struct_to_dict(msg.target)
        service_data = struct_to_dict(msg.service_data)
        if msg.return_response:
            result = await self.hass.services.async_call(
                msg.domain,
                msg.service,
                service_data,
                blocking=True,
                target=target,
                return_response=True,
            )
            response = pb.CallServiceResult()
            response.response.data.CopyFrom(dict_to_struct(result or {}))
            return response
        await self.hass.services.async_call(
            msg.domain,
            msg.service,
            service_data,
            blocking=True,
            target=target,
        )
        return pb.CallServiceResult()


def _entry_from_proto(msg: pb.EntrySetup) -> ConfigEntry:
    """Rebuild a :class:`ConfigEntry` from the typed ``EntrySetup`` message.

    Only fields the integration's setup hooks need are surfaced — the
    sandbox does not persist entries or track update listeners.
    """
    return ConfigEntry(
        version=msg.version,
        minor_version=msg.minor_version,
        domain=msg.domain,
        title=msg.title,
        data=MappingProxyType(struct_to_dict(msg.data)),
        options=MappingProxyType(struct_to_dict(msg.options)),
        source=msg.source,
        unique_id=msg.unique_id if msg.HasField("unique_id") else None,
        entry_id=msg.entry_id,
        discovery_keys=MappingProxyType({}),
        subentries_data=None,
        state=ConfigEntryState.NOT_LOADED,
    )


__all__ = ["EntryRunner"]
