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

The Store routing handlers (``sandbox/store_load`` /
``store_save`` / ``store_remove``) are backed by a per-group
:class:`_SandboxStoreServer`, writing each key to
``<config>/.storage/sandbox/<group>/<key>``.
Scope isolation is by construction — each bridge owns one channel for
one group, so a sandbox can't reach another sandbox's files.
"""

from collections import OrderedDict
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging
import os
from pathlib import Path
from typing import Any, NamedTuple

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import (
    Context,
    HomeAssistant,
    ServiceCall,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, json as json_helper
from homeassistant.helpers.entity_component import DATA_INSTANCES, EntityComponent
from homeassistant.helpers.entity_platform import EntityPlatform
from homeassistant.helpers.storage import STORAGE_DIR
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util, json as json_util
from homeassistant.util.file import write_utf8_file_atomic

from ._proto import sandbox_pb2 as pb
from .channel import Channel, ChannelClosedError, ChannelRemoteError
from .const import UNIQUE_ID_SEPARATOR
from .messages import dict_to_struct, listvalue_to_list, struct_to_dict
from .protocol import (
    MSG_CALL_SERVICE,
    MSG_FIRE_EVENT,
    MSG_REGISTER_ENTITY,
    MSG_REGISTER_SERVICE,
    MSG_STATE_CHANGED,
    MSG_STORE_LOAD,
    MSG_STORE_REMOVE,
    MSG_STORE_SAVE,
    MSG_UNREGISTER_ENTITY,
    MSG_UNREGISTER_SERVICE,
)
from .schema_bridge import reconstruct_schema

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


class _CachedContext(NamedTuple):
    """A remembered Context plus the instant its TTL lapses."""

    context: Context
    expires_at: datetime


@dataclass
class SandboxEntityDescription:
    """Snapshot of a sandbox-side entity, sent at registration time."""

    entry_id: str
    domain: str
    sandbox_entity_id: str
    unique_id: str | None = None
    name: str | None = None
    icon: str | None = None
    has_entity_name: bool = False
    entity_category: str | None = None
    device_class: str | None = None
    supported_features: int = 0
    capabilities: dict[str, Any] = field(default_factory=dict)
    initial_state: str | None = None
    initial_attributes: dict[str, Any] = field(default_factory=dict)
    device_info: dict[str, Any] | None = None
    device_id: str | None = None

    @classmethod
    def from_proto(cls, msg: pb.EntityDescription) -> SandboxEntityDescription:
        """Build a description from the typed ``EntityDescription`` message.

        Flattens the nested ``EntityInfo`` / ``InitialState`` sub-messages back
        into the flat shape the proxy entities consume.
        """
        description = msg.info.description
        initial = msg.initial
        device_info = (
            _deserialise_device_info(msg.info.device_info)
            if msg.info.HasField("device_info")
            else None
        )
        return cls(
            entry_id=msg.entry_id,
            domain=msg.domain,
            sandbox_entity_id=msg.sandbox_entity_id,
            unique_id=msg.unique_id if msg.HasField("unique_id") else None,
            name=description.name if description.HasField("name") else None,
            icon=description.icon if description.HasField("icon") else None,
            has_entity_name=msg.has_entity_name,
            entity_category=(
                description.entity_category
                if description.HasField("entity_category")
                else None
            ),
            device_class=(
                description.device_class
                if description.HasField("device_class")
                else None
            ),
            supported_features=description.supported_features,
            capabilities=struct_to_dict(initial.capabilities),
            initial_state=initial.state if initial.HasField("state") else None,
            initial_attributes=struct_to_dict(initial.attributes),
            device_info=device_info,
        )


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

        self._store_server = _SandboxStoreServer(hass, group)

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
        channel.register(MSG_STATE_CHANGED, self._handle_state_changed)
        channel.register(MSG_REGISTER_SERVICE, self._handle_register_service)
        channel.register(MSG_UNREGISTER_SERVICE, self._handle_unregister_service)
        channel.register(MSG_FIRE_EVENT, self._handle_fire_event)
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
        self._remember_context(context)
        return await self._raw_call_service(
            domain=domain,
            service=service,
            target={"entity_id": [sandbox_entity_id]},
            service_data=service_data,
            context_id=context.id if context is not None else None,
            return_response=return_response,
        )

    async def _raw_call_service(
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
            target=dict_to_struct(target),
            service_data=dict_to_struct(service_data),
            return_response=return_response,
        )
        if context_id is not None:
            request.context_id = context_id
        try:
            return await self.channel.call(MSG_CALL_SERVICE, request)
        except ChannelRemoteError as err:
            raise _translate_remote_error(err) from err
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
    def _remember_context(self, context: Context | None) -> None:
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
        contexts = self._contexts
        contexts[context.id] = _CachedContext(context, now + _CONTEXT_TTL)
        contexts.move_to_end(context.id)
        # TTL + low volume keep this tiny; the cap is only a sanity backstop.
        while len(contexts) > _CONTEXT_CACHE_MAX:
            contexts.popitem(last=False)

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
        self._contexts[context_id] = _CachedContext(context, now + _CONTEXT_TTL)
        self._contexts.move_to_end(context_id)
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
        await self._ensure_domain_loaded(description.domain)
        # Pre-create the device entry so its id is known before the proxy
        # registers; the framework's own async_get_or_create call inside
        # EntityPlatform.async_add_entities is idempotent on (identifiers,
        # connections) and will reuse the same DeviceEntry.
        if description.device_info is not None:
            try:
                device = dr.async_get(self.hass).async_get_or_create(
                    config_entry_id=description.entry_id,
                    **description.device_info,
                )
            except dr.DeviceInfoError as err:
                raise HomeAssistantError(
                    f"register_entity: invalid device_info for "
                    f"{description.sandbox_entity_id!r}: {err}"
                ) from err
            description.device_id = device.id
        # MSG_REGISTER_ENTITY is an upsert: a re-send for an already-tracked
        # entity (the client re-describes on registry/device updates) refreshes
        # the existing proxy in place rather than adding a duplicate. The
        # device pre-creation above already refreshed the DeviceEntry via the
        # idempotent async_get_or_create.
        existing = self._entities.get(description.sandbox_entity_id)
        if existing is not None:
            existing.sandbox_update_description(description)
            return pb.RegisterEntityResult(entity_id=existing.entity_id or "")
        proxy = self._build_proxy(description)
        platform = self._ensure_platform(entry, description.domain)
        await platform.async_add_entities([proxy])
        self._entities[description.sandbox_entity_id] = proxy
        return pb.RegisterEntityResult(entity_id=proxy.entity_id or "")

    async def _ensure_domain_loaded(self, domain: str) -> None:
        """Make sure the domain's :class:`EntityComponent` is loaded on main."""
        components = self.hass.data.get(DATA_INSTANCES, {})
        if domain in components:
            return
        # Empty config — we never own the domain ourselves; we just want
        # the EntityComponent so we can attach a proxy platform to it.
        await async_setup_component(self.hass, domain, {})

    async def _handle_unregister_entity(
        self, msg: pb.UnregisterEntity
    ) -> pb.UnregisterEntityResult:
        sandbox_entity_id = msg.sandbox_entity_id
        proxy = self._entities.pop(sandbox_entity_id, None)
        if proxy is None:
            return pb.UnregisterEntityResult(ok=True)
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

    async def _handle_state_changed(self, msg: pb.StateChanged) -> None:
        proxy = self._entities.get(msg.sandbox_entity_id)
        if proxy is None:
            return
        state_str = msg.state if msg.HasField("state") else None
        attributes = struct_to_dict(msg.attributes)
        context = (
            self._resolve_context(msg.context_id)
            if msg.HasField("context_id")
            else None
        )
        proxy.sandbox_apply_state(state_str, attributes, context)

    async def _handle_register_service(
        self, msg: pb.RegisterService
    ) -> pb.RegisterServiceResult:
        """Mirror a sandbox-registered service onto main's service registry.

        The handler that gets installed forwards every call back over
        the shared ``sandbox/call_service`` channel, so the
        integration's real handler (and its real schema) runs on the
        sandbox side. Exception translation reuses
        :func:`_translate_remote_error`.

        If a service with the same ``(domain, service)`` already exists
        on main (e.g. the host ``light`` EntityComponent registered
        ``light.turn_on`` for our proxy entities, or another integration
        already owns the slot) we skip the install — the existing
        handler stays in charge.
        """
        domain = msg.domain.lower()
        service = msg.service.lower()
        supports_response = _parse_supports_response(msg.supports_response)
        if self.hass.services.has_service(domain, service):
            _LOGGER.debug(
                "SandboxBridge[%s]: %s.%s already on main, not replacing",
                self.group,
                domain,
                service,
            )
            return pb.RegisterServiceResult(ok=True, installed=False)

        forwarder = _build_service_forwarder(self, domain, service, supports_response)
        schema = reconstruct_schema(listvalue_to_list(msg.schema))
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
        data = await self._store_server.async_load(_validate_key(msg.key))
        result = pb.StoreLoadResult()
        if data is not None:
            result.data.update(data)
        return result

    async def _handle_store_save(self, msg: pb.StoreSave) -> pb.StoreSaveResult:
        """Persist a sandbox-side ``Store.async_save`` flush."""
        await self._store_server.async_save(
            _validate_key(msg.key), struct_to_dict(msg.data)
        )
        return pb.StoreSaveResult(ok=True)

    async def _handle_store_remove(self, msg: pb.StoreRemove) -> pb.StoreRemoveResult:
        """Drop the on-disk file for a sandbox-side ``Store.async_remove``."""
        await self._store_server.async_remove(_validate_key(msg.key))
        return pb.StoreRemoveResult(ok=True)

    async def _handle_fire_event(self, msg: pb.FireEvent) -> None:
        """Re-fire a sandbox-side event on main's bus.

        The sandbox tags every push with ``event_type`` + ``event_data`` and,
        optionally, a ``context_id``. Main resolves that id to an authoritative
        Context — restoring the original attribution for an id it handed down,
        or a fresh ``user_id=None`` Context otherwise. The sandbox can never
        inject a ``parent_id`` / ``user_id``.
        """
        event_data = struct_to_dict(msg.event_data)
        context = (
            self._resolve_context(msg.context_id)
            if msg.HasField("context_id")
            else None
        )
        self.hass.bus.async_fire(msg.event_type, event_data, context=context)

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
        return platform

    def _build_proxy(self, description: SandboxEntityDescription) -> Any:
        from .entity import build_proxy  # noqa: PLC0415 — break import cycle

        return build_proxy(self, description)

    async def async_unload_entry(self, entry: ConfigEntry) -> None:
        """Drop every platform and proxy this bridge added for ``entry``."""
        domains = [d for (eid, d) in list(self._platforms) if eid == entry.entry_id]
        for domain in domains:
            platform = self._platforms.pop((entry.entry_id, domain), None)
            if platform is None:
                continue
            await platform.async_destroy()
            component: EntityComponent[Any] | None = self.hass.data.get(
                DATA_INSTANCES, {}
            ).get(domain)
            if component is not None:
                # Mirror the EntityComponent.async_unload_entry side-effect.
                component._platforms.pop(entry.entry_id, None)  # noqa: SLF001
        # Forget proxies that were owned by this entry.
        survivors = {
            sid: proxy
            for sid, proxy in self._entities.items()
            if getattr(proxy.description, "entry_id", None) != entry.entry_id
        }
        self._entities = survivors


_STORE_KEY_FORBIDDEN = ("/", "\\", "\x00")


def _validate_key(key: str) -> str:
    """Validate a store ``key`` from the wire.

    Defends the host filesystem from a compromised sandbox: a key must
    be a non-empty string with no path separators, no null bytes, and
    no parent-directory hop. Anything else trips a
    :class:`HomeAssistantError`, which the channel framework turns into
    a remote-error frame for the sandbox.
    """
    if not key:
        raise HomeAssistantError("store request: missing 'key'")
    if any(ch in key for ch in _STORE_KEY_FORBIDDEN):
        raise HomeAssistantError(f"store request: invalid key {key!r}")
    if key in {".", ".."} or key.startswith(".."):
        raise HomeAssistantError(f"store request: invalid key {key!r}")
    return key


class _SandboxStoreServer:
    """Per-group store backend on main.

    Each :class:`SandboxBridge` owns one of these. The bridge's channel
    is dedicated to one sandbox group, so scope isolation is enforced by
    construction: sandbox "built-in" only ever talks to its own bridge,
    which only ever reads/writes ``<config>/.storage/sandbox/built-in/``.
    Cross-group access requires forging a channel, which the sandbox
    cannot do.
    """

    def __init__(self, hass: HomeAssistant, group: str) -> None:
        """Pin the storage directory to ``<config>/.storage/sandbox/<group>``."""
        self.hass = hass
        self.group = group
        self._dir = Path(hass.config.path(STORAGE_DIR, "sandbox", group))

    def _path_for(self, key: str) -> Path:
        # ``_require_key`` has already rejected slashes / ``..`` / NUL.
        return self._dir / key

    async def async_load(self, key: str) -> dict[str, Any] | None:
        """Return the wrapped Store payload or ``None`` if missing."""
        path = self._path_for(key)
        try:
            data = await self.hass.async_add_executor_job(
                json_util.load_json, str(path), None
            )
        except HomeAssistantError as err:
            _LOGGER.warning(
                "Sandbox %s store_load(%s) failed: %s", self.group, key, err
            )
            return None
        if data is None or data == {}:
            return None
        if not isinstance(data, dict):
            _LOGGER.warning(
                "Sandbox %s store_load(%s): non-dict on disk (%s)",
                self.group,
                key,
                type(data).__name__,
            )
            return None
        return data

    async def async_save(self, key: str, data: dict[str, Any]) -> None:
        """Write the wrapped Store payload atomically."""
        path = self._path_for(key)
        await self.hass.async_add_executor_job(self._write_sync, path, data)

    def _write_sync(self, path: Path, data: dict[str, Any]) -> None:
        os.makedirs(path.parent, exist_ok=True)
        mode, json_data = json_helper.prepare_save_json(data, encoder=None)
        write_utf8_file_atomic(str(path), json_data, False, mode=mode)

    async def async_remove(self, key: str) -> None:
        """Unlink the file backing ``key`` if it exists."""
        path = self._path_for(key)
        await self.hass.async_add_executor_job(self._remove_sync, path)

    def _remove_sync(self, path: Path) -> None:
        try:
            os.unlink(path)
        except FileNotFoundError:
            return


_DEVICE_INFO_STR_FIELDS = (
    "name",
    "manufacturer",
    "model",
    "model_id",
    "sw_version",
    "hw_version",
    "serial_number",
    "suggested_area",
    "configuration_url",
    "default_name",
    "default_manufacturer",
    "default_model",
    "translation_key",
)


def _deserialise_device_info(info: pb.DeviceInfo) -> dict[str, Any] | None:
    """Rebuild a ``DeviceInfo`` TypedDict from the typed proto.

    ``identifiers`` / ``connections`` come back as sets of tuples and
    ``via_device`` as a tuple — the shapes
    :func:`device_registry.async_get_or_create` validates. ``entry_type`` is
    rebuilt as a :class:`DeviceEntryType` enum value.
    """
    out: dict[str, Any] = {}
    if info.identifiers:
        out["identifiers"] = {(pair.key, pair.value) for pair in info.identifiers}
    if info.connections:
        out["connections"] = {(pair.key, pair.value) for pair in info.connections}
    if info.HasField("via_device"):
        out["via_device"] = (info.via_device.key, info.via_device.value)
    if info.entry_type:
        try:
            out["entry_type"] = dr.DeviceEntryType(info.entry_type)
        except ValueError:
            _LOGGER.debug(
                "register_entity: unknown entry_type %r — dropping", info.entry_type
            )
    for field_name in _DEVICE_INFO_STR_FIELDS:
        value = getattr(info, field_name)
        if value:
            out[field_name] = value
    return out or None


def _parse_supports_response(value: Any) -> SupportsResponse:
    """Coerce the wire ``supports_response`` field into the enum."""
    if isinstance(value, SupportsResponse):
        return value
    if value is None:
        return SupportsResponse.NONE
    try:
        return SupportsResponse(str(value).lower())
    except ValueError:
        return SupportsResponse.NONE


def _build_service_forwarder(
    bridge: SandboxBridge,
    domain: str,
    service: str,
    supports_response: SupportsResponse,
):
    """Return a callable suitable for :meth:`ServiceRegistry.async_register`.

    The forwarder rebuilds the original service-call payload and ships it
    back over the sandbox's shared ``sandbox/call_service`` channel.
    Schema validation already ran on the way in (main's registry runs
    ``schema=None`` because the sandbox owns the schema); the sandbox
    runs the real handler against its own entities and registry.
    """

    async def _forward(call: ServiceCall) -> Any:
        # Remember the real (main-issued) Context so the sandbox echoing this
        # id back on a derived state/event restores it verbatim.
        bridge._remember_context(call.context)  # noqa: SLF001
        response = await bridge._raw_call_service(  # noqa: SLF001
            domain=domain,
            service=service,
            target=_target_from_call(call),
            service_data=dict(call.data),
            context_id=call.context.id if call.context is not None else None,
            return_response=call.return_response,
        )
        if supports_response is SupportsResponse.NONE:
            return None
        if response.HasField("response"):
            return struct_to_dict(response.response.data)
        return None

    return _forward


def _target_from_call(call: ServiceCall) -> dict[str, Any]:
    """Extract a ``target`` dict from the (already-validated) service call."""
    target: dict[str, Any] = {}
    if not call.data:
        return target
    for key in ("entity_id", "area_id", "device_id", "floor_id", "label_id"):
        value = call.data.get(key)
        if value is None:
            continue
        target[key] = list(value) if isinstance(value, (list, tuple, set)) else value
    return target


def _rebuild_invalid(data: Mapping[str, Any]) -> vol.Invalid:
    """Rebuild a single :class:`vol.Invalid` from its serialized payload."""
    path = data.get("path") or None
    return vol.Invalid(data.get("msg", ""), path=path)


def _translate_remote_error(err: ChannelRemoteError) -> Exception:
    """Map a sandbox-side exception class name to a sensible main-side one.

    Service-handler errors come back from the sandbox as whatever
    ``services.async_call`` raised — most often :class:`vol.Invalid`. When
    the error frame carries structured ``error_data`` (set for voluptuous
    errors), the original :class:`vol.Invalid` / :class:`vol.MultipleInvalid`
    is rebuilt with its ``path`` intact — callers on main (service/flow
    framework) handle real voluptuous errors correctly. Older/edge frames
    without ``error_data`` fall back to the class-name mapping. Anything we
    don't have a mapping for surfaces as a plain :class:`HomeAssistantError`
    with the remote message preserved.
    """
    if (error_data := err.error_data) is not None:
        kind = error_data.get("kind")
        if kind == "invalid":
            return _rebuild_invalid(error_data)
        if kind == "multiple":
            return vol.MultipleInvalid(
                [_rebuild_invalid(child) for child in error_data.get("errors", [])]
            )
    name = err.error_type or ""
    msg = err.error
    if name in {"Invalid", "MultipleInvalid"}:
        return TypeError(msg)
    if name in {"ServiceNotFound", "ServiceValidationError"}:
        return HomeAssistantError(msg)
    if name == "HomeAssistantError":
        return HomeAssistantError(msg)
    return HomeAssistantError(f"sandbox error ({name or 'unknown'}): {msg}")


@callback
def async_create_bridge(
    hass: HomeAssistant, *, group: str, channel: Channel
) -> SandboxBridge:
    """Public constructor used by ``__init__.async_setup``'s channel callback."""
    return SandboxBridge(hass, group=group, channel=channel)


__all__ = [
    "SandboxBridge",
    "SandboxEntityDescription",
    "async_create_bridge",
]
