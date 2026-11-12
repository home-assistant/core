"""Main-side bridge — owns the per-sandbox entity registry + outbound dispatch."""

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
from .entry_sync import EntrySync
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

# Expire old attribution without retaining every Context for the process lifetime.
_CONTEXT_TTL = timedelta(minutes=15)
# Sanity backstop only; the TTL does the real bounding given the low volume.
_CONTEXT_CACHE_MAX = 2048

# Reject lifecycle events even if an owned domain matches their prefix.
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
        self.entry_sync = EntrySync(hass, channel, lambda entry: entry.sandbox == group)
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

        # Invalidate ownership when entries or proxies change.
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

        # Restore attribution only from contexts issued by main.
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
        """Forward one entity service call to the sandbox as a single RPC."""
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
        """Forward one server-side entity query to the sandbox as a single RPC."""
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
        """Drop expired entries from the front of the context cache."""
        contexts = self._contexts
        while contexts:
            key = next(iter(contexts))
            if contexts[key].expires_at > now:
                break
            del contexts[key]

    @callback
    def _store_context(self, key: str, context: Context, now: datetime) -> None:
        """Insert/refresh a cache entry and enforce the size backstop."""
        contexts = self._contexts
        contexts[key] = _CachedContext(context, now + _CONTEXT_TTL)
        contexts.move_to_end(key)
        # TTL + low volume keep this tiny; the cap is only a sanity backstop.
        while len(contexts) > _CONTEXT_CACHE_MAX:
            contexts.popitem(last=False)

    @callback
    def remember_context(self, context: Context | None) -> None:
        """Record a Context main is handing down to the sandbox."""
        if context is None:
            return
        now = dt_util.utcnow()
        self._prune_contexts(now)
        self._store_context(context.id, context, now)

    @callback
    def _resolve_context(self, context_id: str | None) -> Context:
        """Resolve a sandbox-supplied context_id to an authoritative Context."""
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
        # Validate entry ownership before creating entities or devices on main.
        if entry.sandbox != self.group:
            raise HomeAssistantError(
                f"register_entity: entry {description.entry_id!r} not owned by "
                f"group {self.group!r}"
            )
        if (
            description.config_subentry_id is not None
            and description.config_subentry_id not in entry.subentries
        ):
            raise HomeAssistantError("register_entity: unknown config subentry")
        # Namespace IDs because all proxies share the sandbox platform.
        if description.unique_id is not None:
            description.unique_id = (
                f"{entry.domain}{UNIQUE_ID_SEPARATOR}{description.unique_id}"
            )
        # The proxy entity subclasses the domain's *EntityBase* (LightEntity,
        # SwitchEntity, …); for the framework to host it the domain
        # component itself has to be set up so its EntityComponent exists.
        await self._ensure_domain_loaded(
            description.domain,
            # Only the source integration may use a bare component without a local platform.
            allow_bare=description.domain == entry.domain,
        )
        # Create the device first so proxy registration can reuse its registry ID.
        if description.device_info is not None:
            device_registry = dr.async_get(self.hass)
            # Do not merge sandbox devices into devices owned outside this group.
            self._reject_foreign_device_merge(device_registry, description)
            try:
                device_registry.async_get_or_create(
                    config_entry_id=description.entry_id,
                    config_subentry_id=description.config_subentry_id,
                    **description.device_info,
                )
            except dr.DeviceInfoError as err:
                raise HomeAssistantError(
                    f"register_entity: invalid device_info for "
                    f"{description.sandbox_entity_id!r}: {err}"
                ) from err
        # Refresh repeated registrations in place to preserve entity identity.
        existing = self._entities.get(description.sandbox_entity_id)
        if existing is not None:
            existing.sandbox_update_description(description)
            return pb.RegisterEntityResult(entity_id=existing.entity_id or "")
        proxy = await self._async_build_proxy(description)
        platform = self._ensure_platform(entry, description.domain)
        await platform.async_add_entities(
            [proxy], config_subentry_id=description.config_subentry_id
        )
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
        """Reject device identifiers or connections claimed outside this group."""
        info = description.device_info or {}
        identifiers: set[tuple[str, str]] = info.get("identifiers") or set()
        connections: set[tuple[str, str]] = info.get("connections") or set()
        if not identifiers and not connections:
            return
        owned_entry_ids = self._owned_entry_ids()
        matches = device_registry.async_get_devices(
            identifiers=identifiers or None, connections=connections or None
        )
        if any(device.config_entry_id not in owned_entry_ids for device in matches):
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
        # Own-domain proxies need a component without running the integration on main.
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
        """Mirror a sandbox-registered service onto main's service registry."""
        domain = msg.domain.lower()
        service = msg.service.lower()
        if domain not in self._owned_domains():
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
        # Worker-owned services arrive dynamically after integration setup.
        # pylint: disable-next=home-assistant-action-registered-outside-services-module
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
        """Return the set of domains this sandbox group legitimately owns."""
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
        """Invalidate the owned-domains cache on any config-entry change."""
        self._owned_domains_cache = None

    @callback
    def _is_event_allowed(self, event_type: str) -> bool:
        """Decide whether the sandbox may fire ``event_type`` on main's bus."""
        if event_type in _DENIED_EVENT_TYPES:
            return False
        return any(
            event_type.startswith(f"{domain}_") for domain in self._owned_domains()
        )

    @callback
    def _handle_fire_event(self, msg: pb.FireEvent) -> None:
        """Re-fire a sandbox-side event on main's bus."""
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
        from .entity import build_proxy, proxy_class_for  # noqa: PLC0415 — deliberate lazy import, see below

        # First use of a domain imports its proxy module (and that domain's
        # component package) — do it off the event loop.
        await self.hass.async_add_import_executor_job(
            proxy_class_for, description.domain
        )
        return build_proxy(self, description)

    @callback
    def async_mark_all_unavailable(self) -> None:
        """Flip every proxy this bridge owns to unavailable."""
        for proxy in self._entities.values():
            proxy.sandbox_set_available(False)

    async def async_unload_entry(self, entry: ConfigEntry) -> None:
        """Drop every platform and proxy this bridge added for ``entry``."""
        await self._async_teardown_entry(entry.entry_id)
        self.entry_sync.forget(entry.entry_id)

    async def async_teardown(self) -> None:
        """Release every proxy + platform registration this bridge owns."""
        entry_ids = {eid for (eid, _domain) in list(self._platforms)}
        entry_ids.update(
            proxy.description.entry_id for proxy in list(self._entities.values())
        )
        for entry_id in entry_ids:
            await self._async_teardown_entry(entry_id)
        # Remove forwarders that still reference the dead channel before restart.
        if self._unsub_core_config is not None:
            self._unsub_core_config()
            self._unsub_core_config = None
        for domain, service in self._mirrored_services:
            if self.hass.services.has_service(domain, service):
                self.hass.services.async_remove(domain, service)
        self._mirrored_services.clear()
        self._unsub_entry_changed()
        await self.entry_sync.async_stop()

    async def _async_teardown_entry(self, entry_id: str) -> None:
        """Remove every platform + proxy this bridge added for one entry."""
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
