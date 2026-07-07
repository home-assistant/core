"""Option A — custom method-forward RPC.

Main proxy entity translates each entity method call into a bespoke
``sandbox/entity_method_call`` RPC carrying ``(entity_id, method, kwargs)``.
The sandbox-side dispatcher looks up the local entity and ``await``-s the
named method directly. Mirror of v1's design.
"""

from typing import Any

from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.core import HomeAssistant, callback

from .synthetic_light import SyntheticLight
from .transport import InProcessTransport

COMMAND_ENTITY_METHOD_CALL = "sandbox/entity_method_call"


class OptionAMainBridge:
    """Wires the main-side transport calls for Option A."""

    def __init__(self, transport: InProcessTransport) -> None:
        """Hold the transport used for outgoing entity-method RPCs."""
        self._transport = transport

    async def call_entity_method(
        self, entity_id: str, method: str, kwargs: dict[str, Any]
    ) -> dict[str, Any]:
        """Forward ``method(**kwargs)`` to the sandbox-side proxy for ``entity_id``."""
        return await self._transport.call(
            COMMAND_ENTITY_METHOD_CALL,
            {"entity_id": entity_id, "method": method, "kwargs": kwargs},
        )


class OptionASandboxBridge:
    """Sandbox-side dispatcher for Option A."""

    def __init__(self, hass: HomeAssistant, transport: InProcessTransport) -> None:
        """Register the entity-method handler against the sandbox transport."""
        self._hass = hass
        self._entities: dict[str, SyntheticLight] = {}
        transport.register_handler(
            COMMAND_ENTITY_METHOD_CALL, self._handle_entity_method
        )

    @callback
    def register(self, light: SyntheticLight) -> None:
        """Map ``entity_id`` → real entity so the dispatcher can find it."""
        assert light.entity_id is not None
        self._entities[light.entity_id] = light

    async def _handle_entity_method(self, payload: dict[str, Any]) -> dict[str, Any]:
        entity = self._entities[payload["entity_id"]]
        method = getattr(entity, payload["method"])
        await method(**payload["kwargs"])
        return {"ok": True}


class OptionALightProxy(LightEntity):
    """Main-side proxy that uses the method-forward RPC for every call."""

    _attr_should_poll = False
    _attr_supported_color_modes = {ColorMode.ONOFF}
    _attr_color_mode = ColorMode.ONOFF
    _attr_has_entity_name = False

    def __init__(
        self,
        unique_id: str,
        name: str,
        sandbox_entity_id: str,
        bridge: OptionAMainBridge,
    ) -> None:
        """Initialise the proxy with its sandbox target entity_id and bridge."""
        self._attr_unique_id = unique_id
        self._attr_name = name
        self._sandbox_entity_id = sandbox_entity_id
        self._bridge = bridge
        self._is_on = False

    @property
    def is_on(self) -> bool:
        """Return the cached on/off state."""
        return self._is_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Forward turn_on to the sandbox via the method-forward RPC."""
        await self._bridge.call_entity_method(
            self._sandbox_entity_id, "async_turn_on", kwargs
        )
        self._is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Forward turn_off to the sandbox via the method-forward RPC."""
        await self._bridge.call_entity_method(
            self._sandbox_entity_id, "async_turn_off", kwargs
        )
        self._is_on = False
        self.async_write_ha_state()
