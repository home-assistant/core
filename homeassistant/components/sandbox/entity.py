"""Remote entity proxies for sandboxed integrations.

When a sandbox registers entities, the sandbox integration creates proxy
Entity instances on the host. These proxies:
- Are added to the domain's EntityComponent via a real EntityPlatform
- Cache state/attributes received from the sandbox
- Forward service calls (turn_on, etc.) to the sandbox via websocket
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
import logging
from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_MODE,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_EFFECT,
    ATTR_EFFECT_LIST,
    ATTR_HS_COLOR,
    ATTR_MAX_COLOR_TEMP_KELVIN,
    ATTR_MIN_COLOR_TEMP_KELVIN,
    ATTR_RGB_COLOR,
    ATTR_RGBW_COLOR,
    ATTR_RGBWW_COLOR,
    ATTR_SUPPORTED_COLOR_MODES,
    ATTR_XY_COLOR,
    ColorMode,
    LightEntity,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback

_LOGGER = logging.getLogger(__name__)


@dataclass
class SandboxEntityDescription:
    """Description of a remote entity from a sandbox."""

    domain: str
    platform: str
    unique_id: str
    sandbox_id: str
    sandbox_entry_id: str
    device_id: str | None = None
    original_name: str | None = None
    original_icon: str | None = None
    entity_category: str | None = None
    supported_features: int = 0
    capabilities: dict[str, Any] = field(default_factory=dict)
    has_entity_name: bool = False


class SandboxEntityManager:
    """Manages proxy entities for a sandbox connection."""

    def __init__(self, hass: HomeAssistant, sandbox_id: str) -> None:
        """Initialize the entity manager."""
        self.hass = hass
        self.sandbox_id = sandbox_id
        self._entities: dict[str, SandboxProxyEntity] = {}
        self._pending_calls: dict[str, asyncio.Future[Any]] = {}
        self._platform_add_callbacks: dict[str, AddEntitiesCallback] = {}
        self._call_id_counter = 0

    @callback
    def register_platform_callback(
        self, domain: str, async_add_entities: AddEntitiesCallback
    ) -> None:
        """Register the async_add_entities callback for a domain."""
        self._platform_add_callbacks[domain] = async_add_entities

    @callback
    def add_entity(self, description: SandboxEntityDescription) -> SandboxProxyEntity:
        """Create a proxy entity (not yet tracked by entity_id)."""
        return _create_proxy_entity(description, self)

    @callback
    def track_entity(self, entity_id: str, entity: SandboxProxyEntity) -> None:
        """Track a proxy entity by its assigned entity_id."""
        self._entities[entity_id] = entity

    @callback
    def get_entity(self, entity_id: str) -> SandboxProxyEntity | None:
        """Get a proxy entity by entity_id."""
        return self._entities.get(entity_id)

    @callback
    def remove_entity(self, entity_id: str) -> None:
        """Remove a proxy entity."""
        self._entities.pop(entity_id, None)

    @callback
    def update_state(
        self, entity_id: str, state: str, attributes: dict[str, Any] | None
    ) -> None:
        """Update a proxy entity's state from sandbox push."""
        entity = self._entities.get(entity_id)
        if entity is None:
            return
        entity.sandbox_update_state(state, attributes or {})

    @callback
    def mark_all_unavailable(self) -> None:
        """Mark all entities as unavailable (sandbox disconnected)."""
        for entity in self._entities.values():
            entity.sandbox_set_available(False)

    @callback
    def mark_all_available(self) -> None:
        """Mark all entities as available (sandbox reconnected)."""
        for entity in self._entities.values():
            entity.sandbox_set_available(True)

    def next_call_id(self) -> str:
        """Generate a unique call ID."""
        self._call_id_counter += 1
        return f"{self.sandbox_id}_{self._call_id_counter}"

    @callback
    def resolve_call(self, call_id: str, result: Any, error: str | None) -> None:
        """Resolve a pending method call from the sandbox."""
        future = self._pending_calls.pop(call_id, None)
        if future is None or future.done():
            return
        if error:
            future.set_exception(Exception(error))
        else:
            future.set_result(result)

    def create_call_future(self, call_id: str) -> asyncio.Future[Any]:
        """Create a future for a pending call."""
        future: asyncio.Future[Any] = self.hass.loop.create_future()
        self._pending_calls[call_id] = future
        return future


class SandboxProxyEntity(Entity):
    """Base class for proxy entities that live on the host."""

    _attr_should_poll = False

    def __init__(
        self,
        description: SandboxEntityDescription,
        manager: SandboxEntityManager,
    ) -> None:
        """Initialize the proxy entity."""
        self._description = description
        self._manager = manager
        self._sandbox_available = True
        self._state_cache: dict[str, Any] = {}
        self._attr_unique_id = description.unique_id
        self._attr_has_entity_name = description.has_entity_name
        if description.original_name:
            self._attr_name = description.original_name
        if description.original_icon:
            self._attr_icon = description.original_icon
        self._attr_supported_features = description.supported_features

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device info to associate with the correct device."""
        if self._description.device_id is None:
            return None
        device_reg = dr.async_get(self.hass)
        device = device_reg.async_get(self._description.device_id)
        if device is None:
            return None
        return DeviceInfo(identifiers=device.identifiers)

    async def async_added_to_hass(self) -> None:
        """Register with entity manager once we have our entity_id."""
        self._manager.track_entity(self.entity_id, self)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._sandbox_available

    @callback
    def sandbox_update_state(self, state: str, attributes: dict[str, Any]) -> None:
        """Update state from sandbox push."""
        self._state_cache.update(attributes)
        self._state_cache["state"] = state
        self.async_write_ha_state()

    @callback
    def sandbox_set_available(self, available: bool) -> None:
        """Set availability."""
        self._sandbox_available = available
        self.async_write_ha_state()

    async def _forward_method(self, method: str, **kwargs: Any) -> Any:
        """Forward a method call to the sandbox entity."""
        from .const import DATA_SANDBOX

        sandbox_data = self.hass.data[DATA_SANDBOX]
        sandbox_info = sandbox_data.sandboxes.get(self._manager.sandbox_id)
        if sandbox_info is None or sandbox_info.send_command is None:
            raise RuntimeError("Sandbox not connected")

        call_id = self._manager.next_call_id()
        future = self._manager.create_call_future(call_id)

        sandbox_info.send_command(
            {
                "type": "call_method",
                "call_id": call_id,
                "entity_id": self.entity_id,
                "method": method,
                "kwargs": kwargs,
            }
        )

        return await asyncio.wait_for(future, timeout=30)


class SandboxLightEntity(SandboxProxyEntity, LightEntity):
    """Proxy for a light entity in a sandbox."""

    def __init__(
        self,
        description: SandboxEntityDescription,
        manager: SandboxEntityManager,
    ) -> None:
        """Initialize the proxy light entity."""
        super().__init__(description, manager)
        from homeassistant.components.light import LightEntityFeature

        self._attr_supported_features = LightEntityFeature(
            description.supported_features
        )

    @property
    def is_on(self) -> bool | None:
        """Return if the light is on."""
        state = self._state_cache.get("state")
        if state is None:
            return None
        return state == "on"

    @property
    def brightness(self) -> int | None:
        """Return the brightness."""
        return self._state_cache.get(ATTR_BRIGHTNESS)

    @property
    def color_mode(self) -> ColorMode | str | None:
        """Return the color mode."""
        return self._state_cache.get(ATTR_COLOR_MODE)

    @property
    def hs_color(self) -> tuple[float, float] | None:
        """Return the HS color."""
        val = self._state_cache.get(ATTR_HS_COLOR)
        return tuple(val) if val else None

    @property
    def rgb_color(self) -> tuple[int, int, int] | None:
        """Return the RGB color."""
        val = self._state_cache.get(ATTR_RGB_COLOR)
        return tuple(val) if val else None

    @property
    def rgbw_color(self) -> tuple[int, int, int, int] | None:
        """Return the RGBW color."""
        val = self._state_cache.get(ATTR_RGBW_COLOR)
        return tuple(val) if val else None

    @property
    def rgbww_color(self) -> tuple[int, int, int, int, int] | None:
        """Return the RGBWW color."""
        val = self._state_cache.get(ATTR_RGBWW_COLOR)
        return tuple(val) if val else None

    @property
    def xy_color(self) -> tuple[float, float] | None:
        """Return the XY color."""
        val = self._state_cache.get(ATTR_XY_COLOR)
        return tuple(val) if val else None

    @property
    def color_temp_kelvin(self) -> int | None:
        """Return the color temperature in kelvin."""
        return self._state_cache.get(ATTR_COLOR_TEMP_KELVIN)

    @property
    def min_color_temp_kelvin(self) -> int:
        """Return the min color temperature."""
        return self._description.capabilities.get(
            ATTR_MIN_COLOR_TEMP_KELVIN, 2000
        )

    @property
    def max_color_temp_kelvin(self) -> int:
        """Return the max color temperature."""
        return self._description.capabilities.get(
            ATTR_MAX_COLOR_TEMP_KELVIN, 6500
        )

    @property
    def effect(self) -> str | None:
        """Return the current effect."""
        return self._state_cache.get(ATTR_EFFECT)

    @property
    def effect_list(self) -> list[str] | None:
        """Return the list of supported effects."""
        return self._description.capabilities.get(ATTR_EFFECT_LIST)

    @property
    def supported_color_modes(self) -> set[ColorMode] | set[str] | None:
        """Return the supported color modes."""
        modes = self._description.capabilities.get(ATTR_SUPPORTED_COLOR_MODES)
        if modes is None:
            return None
        return {ColorMode(m) for m in modes}

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Forward turn_on to sandbox."""
        await self._forward_method("async_turn_on", **kwargs)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Forward turn_off to sandbox."""
        await self._forward_method("async_turn_off", **kwargs)


def _create_proxy_entity(
    description: SandboxEntityDescription,
    manager: SandboxEntityManager,
) -> SandboxProxyEntity:
    """Create the appropriate proxy entity for the domain."""
    if description.domain == "light":
        return SandboxLightEntity(description, manager)
    return SandboxProxyEntity(description, manager)
