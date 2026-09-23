"""Sandbox-side entry runner — loads integrations + drives ``async_setup_entry``.

The manager pushes a serialised :class:`ConfigEntry` via
``sandbox/entry_setup`` (see :mod:`hass_client.messages`). The runner
rebuilds the entry on the sandbox's private :class:`HomeAssistant`,
calls ``hass.config_entries.async_setup`` to load the owning integration,
and reports back. Main holds the canonical entry; the sandbox copy is
ephemeral state used by the integration's lifecycle hooks.
"""

import logging
from types import MappingProxyType

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.discovery_flow import DiscoveryKey
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import DATA_INSTANCES
from homeassistant.util.unit_system import get_unit_system

from ._proto import sandbox_pb2 as pb
from .approved_domains import ApprovedDomains
from .channel import Channel
from .entry_sync import EntrySync
from .messages import (
    MSG_CALL_SERVICE,
    MSG_ENTITY_QUERY,
    MSG_ENTRY_SETUP,
    MSG_ENTRY_UNLOAD,
    decode_json,
    decode_json_dict,
    encode_json,
)
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
        entry_sync: EntrySync | None = None,
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
        self.entry_sync = entry_sync

    def register(self, channel: Channel) -> None:
        """Wire the ``sandbox/entry_*`` + ``call_service`` handlers."""
        channel.register(MSG_ENTRY_SETUP, self._handle_entry_setup)
        channel.register(MSG_ENTRY_UNLOAD, self._handle_entry_unload)
        channel.register(MSG_CALL_SERVICE, self._handle_call_service)
        channel.register(MSG_ENTITY_QUERY, self._handle_entity_query)

    async def _handle_entry_setup(self, msg: pb.EntrySetup) -> pb.EntrySetupResult:
        """Build a :class:`ConfigEntry`, register it, and call async_setup."""
        try:
            entry = _entry_from_proto(msg)
        except (KeyError, TypeError) as err:
            return pb.EntrySetupResult(ok=False, reason=f"bad payload: {err}")

        # Mirror main's core config before setup so the integration computes
        # sun times / distances / unit conversions against main's location
        # and units, not the bare-hass defaults. Idempotent, cheap.
        if msg.HasField("core_config"):
            await apply_core_config(self.hass, msg.core_config)

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
        if (
            existing := config_entries.async_get_entry(entry.entry_id)
        ) is not None and existing.state is not ConfigEntryState.NOT_LOADED:
            return pb.EntrySetupResult(ok=False, reason="entry already loaded")

        # ConfigEntries doesn't expose a "add without persist" hook; the
        # sandbox's instance has no Store backing, so we drop the entry
        # straight into the internal map. `async_setup` then finds it via
        # `async_get_known_entry`.
        config_entries._entries[entry.entry_id] = entry  # noqa: SLF001
        if self.entry_sync is not None:
            self.entry_sync.track(entry)
        try:
            ok = await config_entries.async_setup(entry.entry_id)
            if self.entry_sync is not None:
                await self.entry_sync.flush(entry.entry_id)
        except Exception as err:
            _LOGGER.exception(
                "sandbox entry_setup raised for %s (%s)", entry.title, entry.domain
            )
            if entry.state is ConfigEntryState.LOADED:
                # A failed writeback must not orphan a live integration.
                self.approved.add(entry.domain)
                return pb.EntrySetupResult(
                    ok=False,
                    reason="Configuration writeback failed; unload and reload required",
                )
            # Main owns retries; stop the child timer before removing its entry.
            entry.async_cancel_retry_setup()
            if self.entry_sync is not None:
                self.entry_sync.forget(entry.entry_id)
            config_entries._entries.pop(entry.entry_id, None)  # noqa: SLF001
            return pb.EntrySetupResult(
                ok=False, reason=str(err) or err.__class__.__name__
            )
        if not ok:
            # Same cleanup on a plain failed setup (returns False / SETUP_ERROR
            # / SETUP_RETRY) so the entry_id is free for main's retry.
            entry.async_cancel_retry_setup()
            if self.entry_sync is not None:
                self.entry_sync.forget(entry.entry_id)
            config_entries._entries.pop(entry.entry_id, None)  # noqa: SLF001
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
        if not unloaded:
            return pb.EntryUnloadResult(ok=False)
        if self.entry_sync is not None:
            try:
                await self.entry_sync.flush(entry_id)
            except HomeAssistantError:
                _LOGGER.error("Discarding unacknowledged configuration while unloading %s", entry_id)
            self.entry_sync.forget(entry_id)
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
        target = decode_json_dict(msg.target)
        service_data = decode_json_dict(msg.service_data)
        if msg.return_response:
            result = await self.hass.services.async_call(
                msg.domain,
                msg.service,
                service_data,
                blocking=True,
                target=target,
                return_response=True,
            )
            if self.entry_sync is not None:
                await self.entry_sync.flush()
            response = pb.CallServiceResult()
            # encode_json's as_dict-aware encoder carries rich response values
            # (e.g. {entity_id: BrowseMedia}) in the same wire shape the
            # websocket API would serialise.
            response.response.data = encode_json(result or {})
            return response
        await self.hass.services.async_call(
            msg.domain,
            msg.service,
            service_data,
            blocking=True,
            target=target,
        )
        if self.entry_sync is not None:
            await self.entry_sync.flush()
        return pb.CallServiceResult()

    async def _handle_entity_query(self, msg: pb.EntityQuery) -> pb.EntityQueryResult:
        """Invoke a server-side entity method and return its serialised result.

        Resolves the entity on the private hass by ``sandbox_entity_id``,
        ``getattr``s the named method, and awaits it with the decoded kwargs.
        The return is wrapped as ``{"value": …}`` and run through the same
        ``as_dict``-aware JSON encoder used for service responses, so rich
        types (``SearchMedia``, ``BrowseMedia``, ``Segment`` dataclasses)
        cross verbatim. A raised exception (``ServiceValidationError`` /
        ``BrowseError`` / ``SearchError`` / ``HomeAssistantError`` /
        ``probatio.Invalid``) propagates as a channel error frame, exactly like
        ``call_service``, so main rebuilds the same error shape.
        """
        entity = _resolve_entity(self.hass, msg.sandbox_entity_id)
        method = getattr(entity, msg.method, None)
        if not callable(method):
            raise HomeAssistantError(
                f"entity_query: {msg.sandbox_entity_id!r} has no method {msg.method!r}"
            )
        value = await method(**decode_json_dict(msg.args))
        result = pb.EntityQueryResult()
        result.result = encode_json({"value": value})
        return result


async def apply_core_config(hass: HomeAssistant, cfg: pb.CoreConfig) -> None:
    """Apply main's core-config snapshot to the sandbox's private hass.

    Direct attribute writes, deliberately not ``Config.async_update``: the
    private hass has no Store backing and must not persist the values. This
    function fires no event either — the live-update handler
    (``SandboxRuntime._handle_core_config``) fires
    ``EVENT_CORE_CONFIG_UPDATE`` itself, while the entry_setup snapshot is
    applied silently before setup. The time zone goes through the
    async setter so ``dt_util``'s default timezone follows. Every value comes
    from main's own (validated) config, so a bad unit-system/time-zone name is
    a contract violation and surfaces as a failed entry_setup rather than
    being masked.
    """
    config = hass.config
    if cfg.HasField("latitude"):
        config.latitude = cfg.latitude
    if cfg.HasField("longitude"):
        config.longitude = cfg.longitude
    if cfg.HasField("elevation"):
        config.elevation = int(cfg.elevation)
    if cfg.HasField("location_name"):
        config.location_name = cfg.location_name
    if cfg.HasField("country"):
        config.country = cfg.country
    if cfg.HasField("currency"):
        config.currency = cfg.currency
    if cfg.HasField("language"):
        config.language = cfg.language
    if cfg.HasField("unit_system"):
        config.units = get_unit_system(cfg.unit_system)
    if cfg.HasField("time_zone"):
        await config.async_set_time_zone(cfg.time_zone)


def _resolve_entity(hass: HomeAssistant, entity_id: str) -> Entity:
    """Return the live entity object for ``entity_id`` or raise."""
    domain = entity_id.split(".", 1)[0]
    component = hass.data.get(DATA_INSTANCES, {}).get(domain)
    entity = component.get_entity(entity_id) if component is not None else None
    if entity is None:
        raise HomeAssistantError(f"entity_query: unknown entity_id {entity_id!r}")
    return entity


def _entry_from_proto(msg: pb.EntrySetup) -> ConfigEntry:
    """Rebuild a :class:`ConfigEntry` from the typed ``EntrySetup`` message.

    Main owns persistence; the local copy preserves subentry identities and
    preferences so integrations can use the normal configuration APIs.
    """
    return ConfigEntry(
        version=msg.version,
        minor_version=msg.minor_version,
        domain=msg.domain,
        title=msg.title,
        data=MappingProxyType(decode_json_dict(msg.data)),
        options=MappingProxyType(decode_json_dict(msg.options)),
        source=msg.source,
        unique_id=msg.unique_id if msg.HasField("unique_id") else None,
        entry_id=msg.entry_id,
        discovery_keys=MappingProxyType(
            {
                key: tuple(DiscoveryKey.from_json_dict(item) for item in items)
                for key, items in decode_json_dict(msg.discovery_keys).items()
            }
        ),
        subentries_data=decode_json(msg.subentries) or (),
        pref_disable_new_entities=msg.pref_disable_new_entities,
        pref_disable_polling=msg.pref_disable_polling,
        state=ConfigEntryState.NOT_LOADED,
    )


__all__ = ["EntryRunner"]
