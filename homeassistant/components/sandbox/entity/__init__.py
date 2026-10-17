"""Per-domain proxy entities for sandboxed integrations."""

import contextlib
from enum import IntFlag
import importlib
from typing import TYPE_CHECKING, Any, cast, override

from homeassistant.const import EntityCategory
from homeassistant.core import Context
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import StateType

from ..messages import decode_json_dict

if TYPE_CHECKING:
    from ..bridge import SandboxBridge
    from ..description import SandboxEntityDescription


class SandboxProxyEntity(Entity):
    """Base class for proxy entities backed by a sandboxed entity."""

    _attr_should_poll = False

    # Some domain APIs require an IntFlag rather than an integer feature mask.
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
        """Coerce ``supported_features`` into the domain's IntFlag."""
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
        """Typed domain proxies expose attributes through typed properties."""
        return None

    def _apply_description(self, description: SandboxEntityDescription) -> None:
        """Mirror the registration-carried fields onto the entity attrs."""
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
        # Let platform registration reuse the device established by the bridge.
        self._attr_device_info = (
            cast(DeviceInfo, description.device_info)
            if description.device_info is not None
            else None
        )

    def sandbox_update_description(self, description: SandboxEntityDescription) -> None:
        """Refresh mirrored attributes from a re-sent registration (upsert)."""
        self._apply_description(description)
        if self.hass is not None:
            self.async_write_ha_state()

    def sandbox_apply_state(
        self,
        state: str | None,
        attributes: dict[str, Any],
        context: Context | None = None,
    ) -> None:
        """Update the cache from a sandbox push, and notify HA."""
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
        """Forward a service call to the sandbox."""
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
        """Forward a server-side entity query to the sandbox."""
        return await self._bridge.async_entity_query(
            sandbox_entity_id=self.description.sandbox_entity_id,
            method=method,
            args=args,
            context=self._context,
        )


class GenericSandboxEntity(SandboxProxyEntity):
    """Fallback proxy for domains without a typed module."""

    @property
    @override
    def state(self) -> StateType:
        """Return the pushed state verbatim."""
        state: StateType = self._state_cache.get("state")
        return state

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the pushed attributes verbatim."""
        attrs = {
            key: value for key, value in self._state_cache.items() if key != "state"
        }
        return attrs or None


def build_proxy(
    bridge: SandboxBridge, description: SandboxEntityDescription
) -> SandboxProxyEntity:
    """Return a domain-specific proxy for ``description.domain``."""
    return proxy_class_for(description.domain)(bridge, description)


def proxy_class_for(domain: str) -> type[SandboxProxyEntity]:
    """Resolve (and memoize) the proxy class for one domain."""
    if (cls := _DOMAIN_PROXIES.get(domain)) is not None:
        return cls
    try:
        module = importlib.import_module(f".{domain}", __package__)
    except ImportError:
        cls = GenericSandboxEntity
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
            GenericSandboxEntity,
        )
    return _DOMAIN_PROXIES.setdefault(domain, cls)


_DOMAIN_PROXIES: dict[str, type[SandboxProxyEntity]] = {}


__all__ = [
    "SandboxProxyEntity",
    "build_proxy",
]
