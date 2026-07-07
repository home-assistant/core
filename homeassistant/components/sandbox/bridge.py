"""Main-side bridge — owns the per-sandbox entity registry + outbound dispatch.

Responsibilities:

* Hold a :class:`SandboxBridge` per sandbox group. Each one knows its
  :class:`Channel` plus the set of proxy entities the sandbox has
  registered with it.
* Handle inbound sandbox→main calls:

  - ``sandbox/register_entity`` — instantiate a proxy entity, add it to
    the matching :class:`EntityComponent` via
    :meth:`async_register_remote_platform`, and reply with the assigned
    main-side ``entity_id``.
  - ``sandbox/unregister_entity`` — drop the proxy.
  - ``sandbox/state_changed`` — push state/attributes into the cached
    state of the matching proxy entity.

* Expose :meth:`SandboxBridge.async_call_service` for proxy entities to
  forward action calls back to the sandbox — one RPC per call. (Coalescing
  same-tick calls for the same service into a single multi-entity RPC is a
  possible future optimisation; the first iteration keeps it simple.)
* Translate sandbox-side exceptions back into the exception types proxy
  callers would have raised locally (``vol.Invalid`` → ``TypeError``,
  unknown service / entity → ``HomeAssistantError``).

Split-out companions (mechanical seams, no logic of their own):

* :mod:`.store` — the per-group :class:`SandboxStoreServer` backing the
  ``sandbox/store_load`` / ``store_save`` / ``store_remove`` handlers
  (each key lands at ``<config>/.storage/sandbox/<group>/<key>``) plus
  ``validate_key``.
* :mod:`.service_forwarder` — the mirrored-service forwarder factory and
  the sandbox→main exception translation.
* :mod:`.description` — :class:`SandboxEntityDescription` (the
  ``register_entity`` snapshot) and its ``DeviceInfo`` deserialiser.
"""

from collections import OrderedDict
from datetime import datetime, timedelta
import logging
from typing import Any, NamedTuple

from homeassistant.config_entries import (
    SIGNAL_CONFIG_ENTRY_CHANGED,
    ConfigEntry,
    ConfigEntryChange,
)
from homeassistant.const import (
    EVENT_CALL_SERVICE,
    EVENT_COMPONENT_LOADED,
    EVENT_CORE_CONFIG_UPDATE,
    EVENT_HOMEASSISTANT_CLOSE,
    EVENT_HOMEASSISTANT_FINAL_WRITE,
    EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STARTED,
    EVENT_HOMEASSISTANT_STOP,
    EVENT_SERVICE_REGISTERED,
    EVENT_SERVICE_REMOVED,
    EVENT_STATE_CHANGED,
    EVENT_STATE_REPORTED,
)
from homeassistant.core import CALLBACK_TYPE, Context, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_component import DATA_INSTANCES, EntityComponent
from homeassistant.helpers.entity_platform import EntityPlatform
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from ._proto import sandbox_pb2 as pb
from .channel import Channel, ChannelClosedError, ChannelRemoteError
from .const import UNIQUE_ID_SEPARATOR
from .description import SandboxEntityDescription
from .messages import (
    MSG_CALL_SERVICE,
    MSG_CORE_CONFIG,
    MSG_ENTITY_QUERY,
    MSG_FIRE_EVENT,
    MSG_REGISTER_ENTITY,
    MSG_REGISTER_SERVICE,
    MSG_STATE_CHANGED,
    MSG_STORE_LOAD,
    MSG_STORE_REMOVE,
    MSG_STORE_SAVE,
    MSG_UNREGISTER_ENTITY,
    MSG_UNREGISTER_SERVICE,
    core_config_to_proto,
    decode_json,
    decode_json_dict,
    encode_json,
)
from .schema_bridge import reconstruct_schema
from .service_forwarder import (
    build_service_forwarder,
    parse_supports_response,
    translate_remote_error,
)
from .store import SandboxStoreServer, validate_key

_LOGGER = logging.getLogger(__name__)

_REMOTE_PLATFORM_NAME = "sandbox"

# Lifetime of a remembered context_id → Context mapping. Only contexts main
# hands *down* to the sandbox (service calls) are cached, and the sandbox
# echoes them back within the same operation (seconds), so a 15-minute TTL is
# generous headroom while keeping the cache naturally tiny. A miss is always
# safe — it degrades to a fresh ``user_id=None`` Context — so expiry only ever
# loses attribution on a pathologically delayed echo, never correctness.
_CONTEXT_TTL = timedelta(minutes=15)
# Sanity backstop only; the TTL does the real bounding given the low volume.
_CONTEXT_CACHE_MAX = 2048

# Core/internal event types a sandbox may never fire on main's bus, regardless
# of which domains it owns. The owned-domain ``<domain>_`` prefix rule already
# blocks anything outside an owned namespace, but these are hard-denied so an
# "owned domain" can never alias a control-plane event (e.g. a sandbox owning
# the ``automation`` integration must still not be able to fire
# ``homeassistant_stop`` or ``call_service``). Defense in depth — see
# ``_handle_fire_event`` and ARCHITECTURE §6.
_DENIED_EVENT_TYPES = frozenset(
    {
        EVENT_HOMEASSISTANT_START,
        EVENT_HOMEASSISTANT_STARTED,
        EVENT_HOMEASSISTANT_STOP,
        EVENT_HOMEASSISTANT_FINAL_WRITE,
        EVENT_HOMEASSISTANT_CLOSE,
        EVENT_CALL_SERVICE,
        EVENT_STATE_CHANGED,
        EVENT_STATE_REPORTED,
        EVENT_SERVICE_REGISTERED,
        EVENT_SERVICE_REMOVED,
        EVENT_COMPONENT_LOADED,
        EVENT_CORE_CONFIG_UPDATE,
    }
)


class _CachedContext(NamedTuple):
    """A remembered Context plus the instant its TTL lapses."""

    context: Context
    expires_at: datetime


class SandboxBridge:
    """Per-sandbox-group bridge owning entities + outbound RPC dispatch."""

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        group: str,
        channel: Channel,
    ) -> None:
        """Initialise the bridge for one sandbox group's live channel."""
        self.hass = hass
        self.group = group
        self.channel = channel
        # Map sandbox-side entity_id → live proxy. Used for state-push
        # routing and unregister calls.
        self._entities: dict[str, Any] = {}
        # Map config_entry_id → EntityPlatform we own for that (domain, entry).
        # Keyed by (entry_id, domain) so different domains for the same entry
        # land in their own EntityComponent slot.
        self._platforms: dict[tuple[str, str], EntityPlatform] = {}
        # (domain, service) pairs this bridge has mirrored onto main.
        # Used to clean up on shutdown / unregister.
        self._mirrored_services: set[tuple[str, str]] = set()

        self._store_server = SandboxStoreServer(hass, group)

        # Cached _owned_domains() result; None = dirty, recomputed lazily on
        # the next access. Invalidated on proxy register/unregister, platform
        # creation, entry teardown, and any config-entry change (the dispatcher
        # subscription below) — the inputs the derivation reads.
        self._owned_domains_cache: set[str] | None = None
        self._unsub_entry_changed = async_dispatcher_connect(
            hass, SIGNAL_CONFIG_ENTRY_CHANGED, self._on_config_entry_changed
        )
        # Keep a running sandbox's core config in step with main — the
        # entry_setup snapshot goes stale when the user changes the home
        # location / units / language.
        self._unsub_core_config: CALLBACK_TYPE | None = self.hass.bus.async_listen(
            EVENT_CORE_CONFIG_UPDATE, self._on_core_config_update
        )

        # Context security + restoration: the sandbox only ever sends a
        # context_id (a string) — it can never set parent_id / user_id on the
        # wire. Main records every Context it hands *down* to the sandbox
        # (service forwards, entity service calls) keyed by id; when the
        # sandbox echoes that id back (state_changed / fire_event), main
        # restores the original Context verbatim, so a user-initiated action's
        # attribution survives the round-trip. An id main never issued (or one
        # whose entry has expired) resolves to a brand-new main-owned Context
        # with no fabricated parentage — main never adopts the sandbox's id
        # (it is an untrusted ULID; see ``_resolve_context``). The cache is
        # TTL-bounded (``_CONTEXT_TTL``) and ordered by insertion so expiry
        # pruning is a cheap front-to-back walk; a miss is always safe.
        self._contexts: OrderedDict[str, _CachedContext] = OrderedDict()

        channel.register(MSG_REGISTER_ENTITY, self._handle_register_entity)
        channel.register(MSG_UNREGISTER_ENTITY, self._handle_unregister_entity)
        # State pushes + event re-fires are pure sync work (dict updates +
        # a bus fire) — dispatch them inline in the read loop so per-entity
        # ordering is guaranteed and no task is spawned per frame.
        channel.register_push_inline(MSG_STATE_CHANGED, self._handle_state_changed)
        channel.register(MSG_REGISTER_SERVICE, self._handle_register_service)
        channel.register(MSG_UNREGISTER_SERVICE, self._handle_unregister_service)
        channel.register_push_inline(MSG_FIRE_EVENT, self._handle_fire_event)
        channel.register(MSG_STORE_LOAD, self._handle_store_load)
        channel.register(MSG_STORE_SAVE, self._handle_store_save)
        channel.register(MSG_STORE_REMOVE, self._handle_store_remove)

    async def async_call_service(
        self,
        *,
        domain: str,
        service: str,
        sandbox_entity_id: str,
        service_data: dict[str, Any],
        context: Context | None = None,
        return_response: bool = False,
    ) -> Any:
        """Forward one entity service call to the sandbox as a single RPC.

        ``context`` is the main-side Context driving the entity call. It is
        remembered here (before the id is reduced to a bare wire value) so that
        when the sandbox echoes the same id back on a resulting state change
        or event, :meth:`_resolve_context` restores the original
        ``parent_id`` / ``user_id`` instead of minting a fresh attribution.

        One RPC per call keeps the first iteration simple. Coalescing same-tick
        calls for one service into a single multi-entity RPC (so a 200-entity
        area call pays one round-trip instead of 200) is a possible future
        optimisation — see ``docs/FOLLOWUPS.md``.
        """
        self.remember_context(context)
        return await self.async_raw_call_service(
            domain=domain,
            service=service,
            target={"entity_id": [sandbox_entity_id]},
            service_data=service_data,
            context_id=context.id if context is not None else None,
            return_response=return_response,
        )

    async def async_entity_query(
        self,
        *,
        sandbox_entity_id: str,
        method: str,
        args: dict[str, Any],
        context: Context | None = None,
    ) -> Any:
        """Forward one server-side entity query to the sandbox as a single RPC.

        The companion to :meth:`async_call_service` for the query-shaped entity
        APIs that have no ``SupportsResponse`` service to ride (media search,
        update release notes, vacuum segments, the WS-only calendar event
        edits). ``method`` names the real entity method; ``args`` are its
        kwargs. Like a service call the ``context`` is remembered before its id
        is reduced to a bare wire value, errors translate through the same
        :func:`.service_forwarder.translate_remote_error` /
        ``ChannelClosedError`` paths, and the wrapped ``{"value": …}`` return
        is unwrapped.
        """
        self.remember_context(context)
        request = pb.EntityQuery(
            sandbox_entity_id=sandbox_entity_id,
            method=method,
            args=encode_json(args),
        )
        if context is not None:
            request.context_id = context.id
        try:
            result = await self.channel.call(MSG_ENTITY_QUERY, request)
        except ChannelRemoteError as err:
            raise translate_remote_error(err) from err
        except ChannelClosedError as err:
            raise HomeAssistantError(
                f"Sandbox {self.group!r} channel closed mid-query"
            ) from err
        return decode_json_dict(result.result).get("value")

    async def async_raw_call_service(
        self,
        *,
        domain: str,
        service: str,
        target: dict[str, Any],
        service_data: dict[str, Any],
        context_id: str | None,
        return_response: bool,
    ) -> Any:
        """Send one ``sandbox/call_service`` RPC and translate errors."""
        request = pb.CallService(
            domain=domain,
            service=service,
            target=encode_json(target),
            service_data=encode_json(service_data),
            return_response=return_response,
        )
        if context_id is not None:
            request.context_id = context_id
        try:
            return await self.channel.call(MSG_CALL_SERVICE, request)
        except ChannelRemoteError as err:
            raise translate_remote_error(err) from err
        except ChannelClosedError as err:
            raise HomeAssistantError(
                f"Sandbox {self.group!r} channel closed mid-call"
            ) from err

    def _prune_contexts(self, now: datetime) -> None:
        """Drop expired entries from the front of the context cache.

        The cache is kept ordered by insertion (every write moves its key to
        the end), and the TTL is constant, so insertion order *is* expiry
        order — expired entries always cluster at the front and a single walk
        that stops at the first live entry prunes everything stale.
        """
        contexts = self._contexts
        while contexts:
            key = next(iter(contexts))
            if contexts[key].expires_at > now:
                break
            del contexts[key]

    @callback
    def _store_context(self, key: str, context: Context, now: datetime) -> None:
        """Insert/refresh a cache entry and enforce the size backstop.

        Shared by :meth:`remember_context` (real main-issued contexts) and the
        miss path of :meth:`_resolve_context` (fresh contexts minted for an
        unknown id). Keeps the cache ordered by expiry (move-to-end) and caps
        its size so neither path can grow it without bound — a sandbox flooding
        distinct unknown ``context_id``s is bounded the same as legitimate
        traffic.
        """
        contexts = self._contexts
        contexts[key] = _CachedContext(context, now + _CONTEXT_TTL)
        contexts.move_to_end(key)
        # TTL + low volume keep this tiny; the cap is only a sanity backstop.
        while len(contexts) > _CONTEXT_CACHE_MAX:
            contexts.popitem(last=False)

    @callback
    def remember_context(self, context: Context | None) -> None:
        """Record a Context main is handing down to the sandbox.

        Keyed by its (trusted, main-issued) id so an echoed id resolves back
        to the original Context, restoring ``parent_id`` / ``user_id``. The
        entry lives for ``_CONTEXT_TTL``; re-recording refreshes it and moves
        it to the end so the cache stays ordered by expiry. Expiry only loses
        attribution on a later echo (it degrades to a fresh Context), never
        correctness.
        """
        if context is None:
            return
        now = dt_util.utcnow()
        self._prune_contexts(now)
        self._store_context(context.id, context, now)

    @callback
    def _resolve_context(self, context_id: str | None) -> Context:
        """Resolve a sandbox-supplied context_id to an authoritative Context.

        The sandbox can never set ``parent_id`` / ``user_id`` on the wire —
        main owns that. A context_id main handed down (and still remembers)
        resolves back to the original Context verbatim, so a user-initiated
        action's attribution survives the round-trip.

        An id main never issued — or whose entry has expired — yields a
        **brand-new** main-owned ``Context(user_id=None)``: a fresh
        main-generated id, no fabricated parentage. Main never adopts the
        sandbox-supplied id: context ids are ULIDs carrying an embedded
        millisecond timestamp, and main cannot trust the sandbox's clock (a
        crafted id could back- or forward-date the event for recorder /
        logbook ordering). The sandbox string is used only as the cache
        **key**, never as the resulting Context's identity. Caching the fresh
        context under that key lets repeated echoes within one operation map
        to the same stable Context.
        """
        now = dt_util.utcnow()
        self._prune_contexts(now)
        if context_id is None:
            return Context(user_id=None)
        cached = self._contexts.get(context_id)
        if cached is not None:
            return cached.context
        context = Context(user_id=None)
        self._store_context(context_id, context, now)
        return context

    async def _handle_register_entity(
        self, msg: pb.EntityDescription
    ) -> pb.RegisterEntityResult:
        description = SandboxEntityDescription.from_proto(msg)
        entry = self.hass.config_entries.async_get_entry(description.entry_id)
        if entry is None:
            raise HomeAssistantError(
                f"register_entity: unknown entry_id {description.entry_id!r}"
            )
        # Trust the entry_id only after re-deriving ownership from main-side
        # state: the sandbox may register entities *only* for entries main
        # routed to this very group. Without this a compromised sandbox could
        # attach entities (and pre-create devices) against a victim
        # integration's config entry. ``entry.sandbox`` is set by main at flow
        # completion, never by the sandbox.
        if entry.sandbox != self.group:
            raise HomeAssistantError(
                f"register_entity: entry {description.entry_id!r} not owned by "
                f"group {self.group!r}"
            )
        # Namespace the proxy unique_id with the source integration domain so
        # two integrations in one group reusing the same unique_id don't
        # collide on the shared sandbox platform_name. A None unique_id
        # stays None (the entity opts out of the registry).
        if description.unique_id is not None:
            description.unique_id = (
                f"{entry.domain}{UNIQUE_ID_SEPARATOR}{description.unique_id}"
            )
        # The proxy entity subclasses the domain's *EntityBase* (LightEntity,
        # SwitchEntity, …); for the framework to host it the domain
        # component itself has to be set up so its EntityComponent exists.
        await self._ensure_domain_loaded(
            description.domain,
            # Only the entry's own integration domain may fall back to a
            # bare EntityComponent — anything else must be a real,
            # loadable platform domain, or a compromised sandbox could
            # mint entities in arbitrary made-up domains.
            allow_bare=description.domain == entry.domain,
        )
        # Pre-create the device entry so its id is known before the proxy
        # registers; the framework's own async_get_or_create call inside
        # EntityPlatform.async_add_entities is idempotent on (identifiers,
        # connections) and will reuse the same DeviceEntry.
        if description.device_info is not None:
            device_registry = dr.async_get(self.hass)
            # ``async_get_or_create`` merges into an existing device that shares
            # the supplied identifiers/connections, adding our entry to its
            # config_entries set. Refuse to merge into a device already owned by
            # an entry outside this group, so a sandbox cannot hijack a foreign
            # integration's device with crafted identifiers. The device stays
            # scoped to the (now-verified-owned) entry.
            self._reject_foreign_device_merge(device_registry, description)
            try:
                device_registry.async_get_or_create(
                    config_entry_id=description.entry_id,
                    **description.device_info,
                )
            except dr.DeviceInfoError as err:
                raise HomeAssistantError(
                    f"register_entity: invalid device_info for "
                    f"{description.sandbox_entity_id!r}: {err}"
                ) from err
        # MSG_REGISTER_ENTITY is an upsert: a re-send for an already-tracked
        # entity (the client re-describes on registry/device updates) refreshes
        # the existing proxy in place rather than adding a duplicate. The
        # device pre-creation above already refreshed the DeviceEntry via the
        # idempotent async_get_or_create.
        existing = self._entities.get(description.sandbox_entity_id)
        if existing is not None:
            existing.sandbox_update_description(description)
            return pb.RegisterEntityResult(entity_id=existing.entity_id or "")
        proxy = await self._async_build_proxy(description)
        platform = self._ensure_platform(entry, description.domain)
        await platform.async_add_entities([proxy])
        self._entities[description.sandbox_entity_id] = proxy
        self._owned_domains_cache = None
        return pb.RegisterEntityResult(entity_id=proxy.entity_id or "")

    @callback
    def _owned_entry_ids(self) -> set[str]:
        """Return the entry_ids of every config entry main routed to this group."""
        return {
            entry.entry_id
            for entry in self.hass.config_entries.async_entries()
            if entry.sandbox == self.group
        }

    @callback
    def _reject_foreign_device_merge(
        self,
        device_registry: dr.DeviceRegistry,
        description: SandboxEntityDescription,
    ) -> None:
        """Reject a device pre-create that would merge into a foreign entry.

        ``async_get_or_create`` matches an existing device by any shared
        identifier or connection and adds our config entry to it. If that
        device already belongs to a config entry outside this sandbox group,
        merging would let a compromised sandbox graft onto (and thereby reach)
        a foreign integration's device. We refuse — the sandbox may only touch
        devices that are unowned or already owned by one of *its* entries.
        """
        info = description.device_info or {}
        identifiers: set[tuple[str, str]] = info.get("identifiers") or set()
        connections: set[tuple[str, str]] = info.get("connections") or set()
        if not identifiers and not connections:
            return
        existing = device_registry.async_get_device(
            identifiers=identifiers or None, connections=connections or None
        )
        if existing is None:
            return
        foreign = existing.config_entries - self._owned_entry_ids()
        if foreign:
            raise HomeAssistantError(
                f"register_entity: device for "
                f"{description.sandbox_entity_id!r} already belongs to a config "
                f"entry outside group {self.group!r}; refusing to merge"
            )

    async def _ensure_domain_loaded(self, domain: str, *, allow_bare: bool) -> None:
        """Make sure the domain's :class:`EntityComponent` is loaded on main."""
        components = self.hass.data.get(DATA_INSTANCES, {})
        if domain in components:
            return
        # Empty config — we never own the domain ourselves; we just want
        # the EntityComponent so we can attach a proxy platform to it.
        await async_setup_component(self.hass, domain, {})
        if domain in self.hass.data.get(DATA_INSTANCES, {}) or not allow_bare:
            return
        # An integration's *own* domain (sun.sun, …): its EntityComponent is
        # only built inside its own async_setup_entry, which runs sandboxed —
        # a bare component gives the proxies a home without running any
        # integration code on main. EntityComponent self-registers into
        # DATA_INSTANCES.
        EntityComponent(_LOGGER, domain, self.hass)

    async def _handle_unregister_entity(
        self, msg: pb.UnregisterEntity
    ) -> pb.UnregisterEntityResult:
        sandbox_entity_id = msg.sandbox_entity_id
        proxy = self._entities.pop(sandbox_entity_id, None)
        if proxy is None:
            return pb.UnregisterEntityResult(ok=True)
        self._owned_domains_cache = None
        entity_id = getattr(proxy, "entity_id", None)
        if not entity_id:
            return pb.UnregisterEntityResult(ok=True)
        domain = entity_id.split(".", 1)[0]
        component: EntityComponent[Any] | None = self.hass.data.get(
            DATA_INSTANCES, {}
        ).get(domain)
        if component is not None:
            await component.async_remove_entity(entity_id)
        return pb.UnregisterEntityResult(ok=True)

    @callback
    def _handle_state_changed(self, msg: pb.StateChanged) -> None:
        proxy = self._entities.get(msg.sandbox_entity_id)
        if proxy is None:
            return
        state_str = msg.state if msg.HasField("state") else None
        attributes = decode_json_dict(msg.attributes)
        context = (
            self._resolve_context(msg.context_id)
            if msg.HasField("context_id")
            else None
        )
        # ``attributes`` is a fresh decode built for this push; the proxy
        # takes ownership of it (no defensive copy on either side).
        proxy.sandbox_apply_state(state_str, attributes, context)

    async def _handle_register_service(
        self, msg: pb.RegisterService
    ) -> pb.RegisterServiceResult:
        """Mirror a sandbox-registered service onto main's service registry.

        The handler that gets installed forwards every call back over
        the shared ``sandbox/call_service`` channel, so the
        integration's real handler (and its real schema) runs on the
        sandbox side. Exception translation reuses
        :func:`.service_forwarder.translate_remote_error`.

        The service ``domain`` must be one this group owns (same main-side
        :meth:`_owned_domains` derivation the fire_event gate uses): a
        compromised sandbox may not squat ``persistent_notification.*`` or any
        other ``domain.service`` slot outside the domains main routed to it.
        An unowned domain is rejected with a :class:`HomeAssistantError` (the
        channel turns it into a remote-error frame).

        If a service with the same ``(domain, service)`` already exists
        on main (e.g. the host ``light`` EntityComponent registered
        ``light.turn_on`` for our proxy entities, or another integration
        already owns the slot) we skip the install — the existing
        handler stays in charge.
        """
        domain = msg.domain.lower()
        service = msg.service.lower()
        if domain not in self._owned_domains():
            _LOGGER.warning(
                "SandboxBridge[%s]: refusing register_service for unowned "
                "domain %r (%s.%s)",
                self.group,
                domain,
                domain,
                service,
            )
            raise HomeAssistantError(
                f"register_service: domain {domain!r} not owned by group {self.group!r}"
            )
        supports_response = parse_supports_response(msg.supports_response)
        if self.hass.services.has_service(domain, service):
            _LOGGER.debug(
                "SandboxBridge[%s]: %s.%s already on main, not replacing",
                self.group,
                domain,
                service,
            )
            return pb.RegisterServiceResult(ok=True, installed=False)

        forwarder = build_service_forwarder(self, domain, service, supports_response)
        schema = reconstruct_schema(decode_json(msg.schema))
        self.hass.services.async_register(
            domain,
            service,
            forwarder,
            schema=schema,
            supports_response=supports_response,
        )
        self._mirrored_services.add((domain, service))
        return pb.RegisterServiceResult(ok=True, installed=True)

    async def _handle_unregister_service(
        self, msg: pb.UnregisterService
    ) -> pb.UnregisterServiceResult:
        domain = msg.domain.lower()
        service = msg.service.lower()
        key = (domain, service)
        if key not in self._mirrored_services:
            return pb.UnregisterServiceResult(ok=True, removed=False)
        self._mirrored_services.discard(key)
        if self.hass.services.has_service(domain, service):
            self.hass.services.async_remove(domain, service)
        return pb.UnregisterServiceResult(ok=True, removed=True)

    async def _handle_store_load(self, msg: pb.StoreLoad) -> pb.StoreLoadResult:
        """Serve a sandbox-side ``Store.async_load``."""
        data = await self._store_server.async_load(validate_key(msg.key))
        result = pb.StoreLoadResult()
        if data is not None:
            result.data = encode_json(data)
        return result

    async def _handle_store_save(self, msg: pb.StoreSave) -> pb.StoreSaveResult:
        """Persist a sandbox-side ``Store.async_save`` flush."""
        await self._store_server.async_save(
            validate_key(msg.key), decode_json_dict(msg.data)
        )
        return pb.StoreSaveResult(ok=True)

    async def _handle_store_remove(self, msg: pb.StoreRemove) -> pb.StoreRemoveResult:
        """Drop the on-disk file for a sandbox-side ``Store.async_remove``."""
        await self._store_server.async_remove(validate_key(msg.key))
        return pb.StoreRemoveResult(ok=True)

    async def _on_core_config_update(self, _event: Any) -> None:
        """Push main's updated core config down to the sandbox."""
        try:
            await self.channel.push(
                MSG_CORE_CONFIG, core_config_to_proto(self.hass.config)
            )
        except Exception:  # noqa: BLE001
            # A dead channel just means the respawned sandbox will get the
            # fresh snapshot on its next entry_setup.
            _LOGGER.debug(
                "SandboxBridge[%s]: core-config push failed (channel down?)",
                self.group,
            )

    @callback
    def _owned_domains(self) -> set[str]:
        """Return the set of domains this sandbox group legitimately owns.

        Trust is derived entirely from **main-side** state — never from a value
        the (possibly compromised) sandbox sends:

        * the integration ``domain`` of every config entry main routed to
          *this* group (``entry.sandbox == self.group``); plus
        * the platform domains of the proxy entities this bridge has
          registered (some integrations legitimately fire events / own services
          named for a platform they provide rather than their manifest domain).

        Reused by the ``fire_event`` and ``register_service`` gates so the two
        cannot disagree on what the group is allowed to touch. Called on every
        inbound ``fire_event`` / ``register_service``, so the result is cached
        and only recomputed after one of its inputs changed (proxy
        register/unregister, platform creation, entry teardown, any
        config-entry change).
        """
        if (cached := self._owned_domains_cache) is not None:
            return cached
        domains = {
            entry.domain
            for entry in self.hass.config_entries.async_entries()
            if entry.sandbox == self.group
        }
        domains.update(domain for (_entry_id, domain) in self._platforms)
        domains.update(proxy.description.domain for proxy in self._entities.values())
        self._owned_domains_cache = domains
        return domains

    @callback
    def _on_config_entry_changed(
        self, _change: ConfigEntryChange, _entry: ConfigEntry
    ) -> None:
        """Invalidate the owned-domains cache on any config-entry change.

        Add/remove/update can all move an entry in or out of this group
        (``entry.sandbox``), so any change marks the cache dirty — the next
        :meth:`_owned_domains` access recomputes.
        """
        self._owned_domains_cache = None

    @callback
    def _is_event_allowed(self, event_type: str) -> bool:
        """Decide whether the sandbox may fire ``event_type`` on main's bus.

        A core/control-plane event is denied outright; otherwise the name must
        live in an owned domain's ``<domain>_`` namespace.
        """
        if event_type in _DENIED_EVENT_TYPES:
            return False
        return any(
            event_type.startswith(f"{domain}_") for domain in self._owned_domains()
        )

    @callback
    def _handle_fire_event(self, msg: pb.FireEvent) -> None:
        """Re-fire a sandbox-side event on main's bus.

        The sandbox tags every push with ``event_type`` + ``event_data`` and,
        optionally, a ``context_id``. Main resolves that id to an authoritative
        Context — restoring the original attribution for an id it handed down,
        or a fresh ``user_id=None`` Context otherwise. The sandbox can never
        inject a ``parent_id`` / ``user_id``.

        Main re-derives trust from its own state: the event name must fall in
        the ``<domain>_`` namespace of a domain this group owns and must not be
        a core control-plane event (see :meth:`_is_event_allowed`). A forged
        ``homeassistant_stop`` / ``call_service`` / foreign ``zha_event`` from a
        compromised sandbox is logged and dropped, never re-fired — and never
        raised into the dispatch loop (this is a one-way push).
        """
        event_type = msg.event_type
        if not self._is_event_allowed(event_type):
            _LOGGER.warning(
                "SandboxBridge[%s]: dropping disallowed event %r from sandbox",
                self.group,
                event_type,
            )
            return
        event_data = decode_json_dict(msg.event_data)
        context = (
            self._resolve_context(msg.context_id)
            if msg.HasField("context_id")
            else None
        )
        self.hass.bus.async_fire(event_type, event_data, context=context)

    def _ensure_platform(self, entry: ConfigEntry, domain: str) -> EntityPlatform:
        key = (entry.entry_id, domain)
        existing = self._platforms.get(key)
        if existing is not None:
            return existing
        component: EntityComponent[Any] | None = self.hass.data.get(
            DATA_INSTANCES, {}
        ).get(domain)
        if component is None:
            raise HomeAssistantError(
                f"register_entity: no EntityComponent for {domain!r}; the"
                " host integration is not loaded"
            )
        platform = EntityPlatform(
            hass=self.hass,
            logger=_LOGGER,
            domain=domain,
            platform_name=_REMOTE_PLATFORM_NAME,
            platform=None,
            scan_interval=timedelta(seconds=0),
            entity_namespace=None,
        )
        platform.config_entry = entry
        platform.async_prepare()
        component.async_register_remote_platform(entry, platform)
        self._platforms[key] = platform
        self._owned_domains_cache = None
        return platform

    async def _async_build_proxy(self, description: SandboxEntityDescription) -> Any:
        from .entity import (  # noqa: PLC0415 — deliberate lazy import, see below
            build_proxy,
            proxy_class_for,
        )

        # First use of a domain imports its proxy module (and that domain's
        # component package) — do it off the event loop.
        await self.hass.async_add_import_executor_job(
            proxy_class_for, description.domain
        )
        return build_proxy(self, description)

    @callback
    def async_mark_all_unavailable(self) -> None:
        """Flip every proxy this bridge owns to unavailable.

        Called when the sandbox's channel drops (process exit): the proxies
        would otherwise keep serving the last state they saw — a dead
        sandbox's ``light`` would read ``on`` forever to automations and the
        UI. They flip back to available on respawn via the normal
        register/``state_changed`` round-trip.
        """
        for proxy in self._entities.values():
            proxy.sandbox_set_available(False)

    async def async_unload_entry(self, entry: ConfigEntry) -> None:
        """Drop every platform and proxy this bridge added for ``entry``."""
        await self._async_teardown_entry(entry.entry_id)

    async def async_teardown(self) -> None:
        """Release every proxy + platform registration this bridge owns.

        Called when a sandbox restart hands the integration a fresh
        process: the old bridge's proxy entities and their
        :class:`EntityComponent` platform slots must be torn down so the
        replacement bridge can re-register the same entries without
        tripping the ``"has already been setup!"`` guard.
        """
        entry_ids = {eid for (eid, _domain) in list(self._platforms)}
        entry_ids.update(
            proxy.description.entry_id for proxy in list(self._entities.values())
        )
        for entry_id in entry_ids:
            await self._async_teardown_entry(entry_id)
        # Remove the mirrored service forwarders — each closes over this
        # bridge's (now dead) channel, and a respawned sandbox's
        # re-registration is skipped by the has_service() guard, so a stale
        # forwarder would fail every call until HA restarts.
        if self._unsub_core_config is not None:
            self._unsub_core_config()
            self._unsub_core_config = None
        for domain, service in self._mirrored_services:
            if self.hass.services.has_service(domain, service):
                self.hass.services.async_remove(domain, service)
        self._mirrored_services.clear()
        self._unsub_entry_changed()

    async def _async_teardown_entry(self, entry_id: str) -> None:
        """Remove every platform + proxy this bridge added for one entry.

        Shared by :meth:`async_unload_entry` and :meth:`async_teardown`.
        The :class:`EntityPlatform` is dropped from its
        :class:`EntityComponent` through the public inverse hook
        (:meth:`EntityComponent.async_unregister_remote_platform`) — never a
        private ``_platforms`` poke — and then destroyed, which removes its
        proxy entities from the state machine.
        """
        domains = [d for (eid, d) in list(self._platforms) if eid == entry_id]
        for domain in domains:
            platform = self._platforms.pop((entry_id, domain), None)
            if platform is None:
                continue
            component: EntityComponent[Any] | None = self.hass.data.get(
                DATA_INSTANCES, {}
            ).get(domain)
            if component is not None and platform.config_entry is not None:
                component.async_unregister_remote_platform(platform.config_entry)
            await platform.async_destroy()
        # Forget any proxies that were owned by this entry.
        self._entities = {
            sid: proxy
            for sid, proxy in self._entities.items()
            if proxy.description.entry_id != entry_id
        }
        self._owned_domains_cache = None


@callback
def async_create_bridge(
    hass: HomeAssistant, *, group: str, channel: Channel
) -> SandboxBridge:
    """Public constructor used by ``__init__.async_setup``'s channel callback."""
    return SandboxBridge(hass, group=group, channel=channel)


__all__ = [
    "SandboxBridge",
    "async_create_bridge",
]
