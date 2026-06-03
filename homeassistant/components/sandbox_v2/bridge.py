"""Main-side bridge — owns the per-sandbox entity registry + outbound dispatch.

Responsibilities (Phase 5):

* Hold a :class:`SandboxBridge` per sandbox group. Each one knows its
  :class:`Channel` plus the set of proxy entities the sandbox has
  registered with it.
* Handle inbound sandbox→main calls:

  - ``sandbox_v2/register_entity`` — instantiate a proxy entity, add it to
    the matching :class:`EntityComponent` via
    :meth:`async_register_remote_platform`, and reply with the assigned
    main-side ``entity_id``.
  - ``sandbox_v2/unregister_entity`` — drop the proxy.
  - ``sandbox_v2/state_changed`` — push state/attributes into the cached
    state of the matching proxy entity.

* Expose :meth:`SandboxBridge.async_call_service` for proxy entities to
  forward action calls back to the sandbox. The forwarder coalesces calls
  made within the same event-loop tick using
  :class:`_CallServiceBatcher` so a 200-entity area call pays one RPC
  instead of 200.
* Translate sandbox-side exceptions back into the exception types proxy
  callers would have raised locally (``vol.Invalid`` → ``TypeError``,
  unknown service / entity → ``HomeAssistantError``).

Phase 8 adds the Store routing handlers (``sandbox_v2/store_load`` /
``store_save`` / ``store_remove``). A per-group :class:`_SandboxStoreServer`
backs them, writing each key to ``<config>/.storage/sandbox_v2/<group>/<key>``.
Scope isolation is by construction — each bridge owns one channel for
one group, so a sandbox can't reach another sandbox's files.
"""

import asyncio
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import timedelta
import logging
import os
from pathlib import Path
from typing import Any

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
from homeassistant.util import json as json_util
from homeassistant.util.file import write_utf8_file_atomic

from ._proto import sandbox_v2_pb2 as pb
from .auth import async_get_or_create_sandbox_user
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

_REMOTE_PLATFORM_NAME = "sandbox_v2"


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


class _CallServiceBatcher:
    """Per-loop-tick coalescer keyed by (domain, service, frozen kwargs).

    Proxy entities call :meth:`enqueue` for every method invocation. The
    batcher gathers everything that arrived this tick, fires one
    ``sandbox_v2/call_service`` per (domain, service, kwargs-shape) bucket
    with a multi-entity ``target.entity_id`` list, and resolves all the
    waiting futures with the same response.

    Kwargs are not hashable (they include nested dicts/lists), so the key
    is the JSON-canonical form of the kwargs dict. Only entities that
    happen to use *identical* kwargs collapse into one RPC, which matches
    how an area call resolves: HA applies the same kwargs to every
    targeted entity.
    """

    def __init__(self, bridge: SandboxBridge) -> None:
        """Initialise the batcher with its owning bridge."""
        self._bridge = bridge
        self._buckets: dict[tuple[str, str, str], _BatchBucket] = {}
        self._flush_handle: asyncio.Handle | None = None

    async def enqueue(
        self,
        *,
        domain: str,
        service: str,
        sandbox_entity_id: str,
        service_data: dict[str, Any],
        context_id: str | None = None,
        return_response: bool = False,
    ) -> Any:
        """Queue one entity into the next batched ``call_service`` RPC."""
        import json  # noqa: PLC0415 — local import keeps json off integration boot path

        kwargs_key = json.dumps(
            service_data, sort_keys=True, separators=(",", ":"), default=str
        )
        bucket_key = (domain, service, kwargs_key)
        bucket = self._buckets.get(bucket_key)
        if bucket is None:
            future: asyncio.Future[Any] = asyncio.get_running_loop().create_future()
            bucket = _BatchBucket(
                domain=domain,
                service=service,
                service_data=service_data,
                context_id=context_id,
                return_response=return_response,
                future=future,
            )
            self._buckets[bucket_key] = bucket
        bucket.sandbox_entity_ids.append(sandbox_entity_id)
        self._schedule_flush()
        return await bucket.future

    def _schedule_flush(self) -> None:
        if self._flush_handle is not None:
            return
        loop = asyncio.get_running_loop()
        self._flush_handle = loop.call_soon(self._flush)

    def _flush(self) -> None:
        self._flush_handle = None
        buckets = self._buckets
        self._buckets = {}
        for bucket in buckets.values():
            asyncio.create_task(  # noqa: RUF006 — fire-and-forget; bucket.future is the join point
                self._dispatch(bucket), name="sandbox_v2:call_service:flush"
            )

    async def _dispatch(self, bucket: _BatchBucket) -> None:
        try:
            result = await self._bridge._raw_call_service(  # noqa: SLF001
                domain=bucket.domain,
                service=bucket.service,
                target={"entity_id": bucket.sandbox_entity_ids},
                service_data=bucket.service_data,
                context_id=bucket.context_id,
                return_response=bucket.return_response,
            )
        except BaseException as err:  # noqa: BLE001
            if not bucket.future.done():
                bucket.future.set_exception(err)
            return
        if not bucket.future.done():
            bucket.future.set_result(result)


@dataclass
class _BatchBucket:
    """One coalesced ``sandbox_v2/call_service`` invocation in flight."""

    domain: str
    service: str
    service_data: dict[str, Any]
    context_id: str | None
    return_response: bool
    future: asyncio.Future[Any]
    sandbox_entity_ids: list[str] = field(default_factory=list)


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
        self._batcher = _CallServiceBatcher(self)

        self._store_server = _SandboxStoreServer(hass, group)

        # Context security: the sandbox only ever sends a context_id (a
        # string). Main resolves it to its own authoritative Context, never
        # honouring a sandbox-supplied parent_id / user_id. Resolved contexts
        # are cached so a repeated id maps to one stable Context.
        self._system_user_id: str | None = None
        self._contexts: dict[str, Context] = {}

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
        context_id: str | None = None,
        return_response: bool = False,
    ) -> Any:
        """Forward one entity service call to the sandbox.

        Calls made in the same tick with matching ``(domain, service,
        service_data)`` coalesce into a single RPC with a multi-entity
        target.
        """
        return await self._batcher.enqueue(
            domain=domain,
            service=service,
            sandbox_entity_id=sandbox_entity_id,
            service_data=service_data,
            context_id=context_id,
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
        """Send one ``sandbox_v2/call_service`` RPC and translate errors."""
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

    async def _async_system_user_id(self) -> str:
        """Return (and cache) the sandbox group's system-user id."""
        if self._system_user_id is None:
            user = await async_get_or_create_sandbox_user(self.hass, self.group)
            self._system_user_id = user.id
        return self._system_user_id

    async def _resolve_context(self, context_id: str | None) -> Context:
        """Resolve a sandbox-supplied context_id to an authoritative Context.

        The sandbox can never set ``parent_id`` / ``user_id`` on the wire —
        main owns that. A context_id main has already resolved reuses the same
        Context; an unseen id (or no id) mints a fresh Context attributed to
        the sandbox's system user, with no ``parent_id``.
        """
        user_id = await self._async_system_user_id()
        if context_id is None:
            return Context(user_id=user_id)
        existing = self._contexts.get(context_id)
        if existing is not None:
            return existing
        context = Context(id=context_id, user_id=user_id)
        self._contexts[context_id] = context
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
        # collide on the shared sandbox_v2 platform_name. A None unique_id
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
            await self._resolve_context(msg.context_id)
            if msg.HasField("context_id")
            else None
        )
        proxy.sandbox_apply_state(state_str, attributes, context)

    async def _handle_register_service(
        self, msg: pb.RegisterService
    ) -> pb.RegisterServiceResult:
        """Mirror a sandbox-registered service onto main's service registry.

        The handler that gets installed forwards every call back over
        the shared ``sandbox_v2/call_service`` channel, so the
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
        """Serve a sandbox-side ``Store.async_load`` (Phase 8)."""
        data = await self._store_server.async_load(_validate_key(msg.key))
        result = pb.StoreLoadResult()
        if data is not None:
            result.data.update(data)
        return result

    async def _handle_store_save(self, msg: pb.StoreSave) -> pb.StoreSaveResult:
        """Persist a sandbox-side ``Store.async_save`` flush (Phase 8)."""
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
        optionally, a ``context_id``. Main resolves that id to an
        authoritative Context attributed to the sandbox's system user — the
        sandbox can never inject a ``parent_id`` / ``user_id``.
        """
        event_data = struct_to_dict(msg.event_data)
        context = (
            await self._resolve_context(msg.context_id)
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
    which only ever reads/writes ``<config>/.storage/sandbox_v2/built-in/``.
    Cross-group access requires forging a channel, which the sandbox
    cannot do.
    """

    def __init__(self, hass: HomeAssistant, group: str) -> None:
        """Pin the storage directory to ``<config>/.storage/sandbox_v2/<group>``."""
        self.hass = hass
        self.group = group
        self._dir = Path(hass.config.path(STORAGE_DIR, "sandbox_v2", group))

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
    back over the sandbox's shared ``sandbox_v2/call_service`` channel.
    Schema validation already ran on the way in (main's registry runs
    ``schema=None`` because the sandbox owns the schema); the sandbox
    runs the real handler against its own entities and registry.
    """

    async def _forward(call: ServiceCall) -> Any:
        request = pb.CallService(
            domain=domain,
            service=service,
            service_data=dict_to_struct(dict(call.data)),
            target=dict_to_struct(_target_from_call(call)),
            return_response=call.return_response,
        )
        if call.context is not None:
            request.context_id = call.context.id
        try:
            response = await bridge.channel.call(MSG_CALL_SERVICE, request)
        except ChannelRemoteError as err:
            raise _translate_remote_error(err) from err
        except ChannelClosedError as err:
            raise HomeAssistantError(
                f"Sandbox {bridge.group!r} channel closed during {domain}.{service}"
            ) from err
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
