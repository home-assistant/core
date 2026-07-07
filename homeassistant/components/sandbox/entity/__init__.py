"""Per-domain proxy entities for sandboxed integrations.

The :class:`SandboxProxyEntity` base holds the cached state and the
``async_call_service`` plumbing every proxy shares. Domain-specific
subclasses add typed properties that pull values out of the cache so
service-handler kwarg filtering (``light.filter_turn_on_params``,
``climate`` schema validation, …) and frontend rendering see the same
shape they would for a local entity.

A small "rich" set of domains ships typed proxies; the remaining
domains use the same mechanical pattern.
"""

import contextlib
from enum import IntFlag
import importlib
from typing import TYPE_CHECKING, Any, cast, override

from homeassistant.const import EntityCategory
from homeassistant.core import Context
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from ..messages import decode_json_dict

if TYPE_CHECKING:
    from ..bridge import SandboxBridge
    from ..description import SandboxEntityDescription


class SandboxProxyEntity(Entity):
    """Base class for proxy entities backed by a sandboxed entity."""

    _attr_should_poll = False

    # Domain subclasses set this to their ``<Domain>EntityFeature`` IntFlag so
    # the base coerces ``supported_features`` into it. ``light``'s
    # capability_attributes does ``X in supported_features``, which only works
    # on the flag, not a plain int. ``None`` → leave it a plain int.
    _features_flag: type[IntFlag] | None = None

    def __init__(
        self,
        bridge: SandboxBridge,
        description: SandboxEntityDescription,
    ) -> None:
        """Initialise the proxy entity from its sandbox-side description."""
        self._bridge = bridge
        self.description = description
        self._state_cache: dict[str, Any] = dict(description.initial_attributes)
        if description.initial_state is not None:
            self._state_cache["state"] = description.initial_state
        self._sandbox_available: bool = True

        self._attr_unique_id = description.unique_id
        self._apply_description(description)

    def _coerce_supported_features(self, value: int | None) -> IntFlag | int:
        """Coerce ``supported_features`` into the domain's IntFlag.

        Domains like ``light`` index ``supported_features`` with bitwise
        ``in``, which only works on the IntFlag; ``None`` blows up the check,
        so default to 0. Domains without a ``_features_flag`` keep a plain int.
        """
        features = int(value or 0)
        if self._features_flag is not None:
            return self._features_flag(features)
        return features

    @property
    @override
    def available(self) -> bool:
        """Available iff the sandbox is reachable and the entity has state."""
        if not self._sandbox_available:
            return False
        state = self._state_cache.get("state")
        return state not in (None, "unavailable")

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Sandbox proxies expose attributes through typed properties.

        Anything domain-specific (``brightness``, ``hvac_mode``, …) is
        surfaced by the domain proxy's own ``@property`` declarations
        reading from ``_state_cache``. Returning extras here would
        duplicate those values in the state-machine attributes dict.
        """
        return None

    def _apply_description(self, description: SandboxEntityDescription) -> None:
        """Mirror the registration-carried fields onto the entity attrs.

        Shared by ``__init__`` and the upsert path so init and refresh can't
        drift; clearing is symmetric — a field dropped from a re-sent
        registration clears the mirrored attribute rather than sticking.
        """
        self.description = description
        self._attr_has_entity_name = description.has_entity_name
        self._attr_name = description.name or None
        self._attr_icon = description.icon or None
        self._attr_entity_category = None
        if description.entity_category:
            with contextlib.suppress(ValueError):
                self._attr_entity_category = EntityCategory(description.entity_category)
        self._attr_device_class = description.device_class or None
        self._attr_supported_features = self._coerce_supported_features(
            description.supported_features
        )
        # Surface the sandbox-side DeviceInfo so EntityPlatform's normal
        # async_add_entities path runs dr.async_get_or_create and links
        # the proxy to the matching DeviceEntry (idempotent with the
        # pre-creation the bridge does).
        self._attr_device_info = (
            cast(DeviceInfo, description.device_info)
            if description.device_info is not None
            else None
        )

    def sandbox_update_description(self, description: SandboxEntityDescription) -> None:
        """Refresh mirrored attributes from a re-sent registration (upsert).

        The unique_id is deliberately left untouched — changing it would
        orphan the entity-registry row. State flows via the separate
        ``state_changed`` push path, so only the registration-carried
        fields (name / icon / category / device_class / features /
        device_info) are refreshed here.
        """
        self._apply_description(description)
        if self.hass is not None:
            self.async_write_ha_state()

    def sandbox_apply_state(
        self,
        state: str | None,
        attributes: dict[str, Any],
        context: Context | None = None,
    ) -> None:
        """Update the cache from a sandbox push, and notify HA.

        Ownership contract: the caller hands over ``attributes`` — the bridge
        builds a fresh dict per push, so it becomes the new ``_state_cache``
        without a defensive copy. Callers must not reuse the dict afterwards.

        ``context`` is the main-side authoritative Context the bridge resolved
        from the sandbox's ``context_id`` — the original Context for an id main
        handed down, or a fresh ``user_id=None`` one otherwise, never carrying
        a sandbox-supplied parent_id / user_id. When absent the entity writes
        with its own context as before.
        """
        self._state_cache = attributes
        if state is not None:
            self._state_cache["state"] = state
        if self.hass is not None:
            if context is not None:
                self.async_set_context(context)
            self.async_write_ha_state()

    def sandbox_set_available(self, available: bool) -> None:
        """Toggle availability — used when the sandbox channel drops."""
        if self._sandbox_available == available:
            return
        self._sandbox_available = available
        if self.hass is not None:
            self.async_write_ha_state()

    async def _call_service(
        self, service: str, *, return_response: bool = False, **service_data: Any
    ) -> Any:
        """Forward a service call to the sandbox.

        Domain proxies translate each entity method into one of these
        calls (the spike's Option B); the bridge sends one RPC per call.

        ``self._context`` is the main-side Context the service framework set
        for this call. Passing it lets the bridge remember it, so a state
        change the sandbox derives from this call resolves back to the
        original attribution instead of a fresh context.

        When ``return_response`` is set, the call forwards a
        ``SupportsResponse`` service (``calendar.get_events``,
        ``weather.get_forecasts``, ``media_player.browse_media``) and the
        decoded service-response dict is returned (``{}`` when the sandbox
        sent no response). Otherwise the raw ``CallServiceResult`` is returned
        and ignored by command-style proxies.
        """
        result = await self._bridge.async_call_service(
            domain=self.description.domain,
            service=service,
            sandbox_entity_id=self.description.sandbox_entity_id,
            service_data=service_data,
            context=self._context,
            return_response=return_response,
        )
        if not return_response:
            return result
        if result.HasField("response"):
            return decode_json_dict(result.response.data)
        return {}

    async def _entity_query(self, method: str, **args: Any) -> Any:
        """Forward a server-side entity query to the sandbox.

        The request/response companion to :meth:`_call_service` for the
        query-shaped entity APIs that have no ``SupportsResponse`` service to
        ride. ``method`` names the real entity method to invoke on the sandbox
        side; ``args`` are its kwargs. Returns the deserialised return value
        (``None`` for mutations). ``self._context`` is forwarded so attribution
        survives exactly as it does for a service call.
        """
        return await self._bridge.async_entity_query(
            sandbox_entity_id=self.description.sandbox_entity_id,
            method=method,
            args=args,
            context=self._context,
        )


def build_proxy(
    bridge: SandboxBridge, description: SandboxEntityDescription
) -> SandboxProxyEntity:
    """Return a domain-specific proxy for ``description.domain``.

    Falls back to the generic :class:`SandboxProxyEntity` for a domain
    with no dedicated module.
    """
    return proxy_class_for(description.domain)(bridge, description)


def proxy_class_for(domain: str) -> type[SandboxProxyEntity]:
    """Resolve (and memoize) the proxy class for one domain.

    Imports only the requested domain's proxy module — and through it that
    one domain's component package — on first use. Importing all 31 proxy
    modules eagerly measured ~384 ms / +67 MB on a cold main instance, paid
    inside the first ``register_entity`` RPC; per-domain laziness bounds
    that to the domains a sandbox actually registers. The import itself
    may block briefly, so the bridge warms this from the import executor
    before touching it on the event loop.
    """
    if (cls := _DOMAIN_PROXIES.get(domain)) is not None:
        return cls
    try:
        module = importlib.import_module(f".{domain}", __package__)
    except ImportError:
        cls = SandboxProxyEntity
    else:
        # Each proxy module defines exactly one SandboxProxyEntity subclass.
        cls = next(
            (
                obj
                for obj in vars(module).values()
                if isinstance(obj, type)
                and issubclass(obj, SandboxProxyEntity)
                and obj.__module__ == module.__name__
            ),
            SandboxProxyEntity,
        )
    return _DOMAIN_PROXIES.setdefault(domain, cls)


_DOMAIN_PROXIES: dict[str, type[SandboxProxyEntity]] = {}


__all__ = [
    "SandboxProxyEntity",
    "build_proxy",
]
