"""Option B — action-call forwarding.

The main proxy translates each entity method into a standard
``services.async_call("light", "turn_on", target={...})`` round-trip via the
existing ``sandbox_v2/call_service`` transport. The sandbox runs HA's own
service dispatcher, which resolves the target and invokes ``async_turn_on``
on the real entity. No bespoke entity-method RPC on the wire.
"""

from typing import Any

from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.core import HomeAssistant, callback

from .transport import InProcessTransport

COMMAND_CALL_SERVICE = "sandbox_v2/call_service"


class OptionBMainBridge:
    """Wires the main-side transport calls for Option B."""

    def __init__(self, transport: InProcessTransport) -> None:
        """Hold the transport used for outgoing service-call RPCs."""
        self._transport = transport

    async def call_service(
        self,
        domain: str,
        service: str,
        target: dict[str, Any] | None,
        service_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Forward a service call to the sandbox over the shared transport."""
        return await self._transport.call(
            COMMAND_CALL_SERVICE,
            {
                "domain": domain,
                "service": service,
                "target": target or {},
                "service_data": service_data,
            },
        )


class OptionBSandboxBridge:
    """Sandbox-side handler that just dispatches into the local service registry."""

    def __init__(self, hass: HomeAssistant, transport: InProcessTransport) -> None:
        """Register the call_service handler against the sandbox transport."""
        self._hass = hass
        transport.register_handler(COMMAND_CALL_SERVICE, self._handle_call_service)

    @callback
    def register(self, _entity: Any) -> None:
        """No-op: Option B routes by entity_id through the service dispatcher."""

    async def _handle_call_service(self, payload: dict[str, Any]) -> dict[str, Any]:
        await self._hass.services.async_call(
            payload["domain"],
            payload["service"],
            payload.get("service_data") or {},
            blocking=True,
            target=payload.get("target") or {},
        )
        return {"ok": True}


class OptionBLightProxy(LightEntity):
    """Main-side proxy that forwards every call as a standard light service call."""

    _attr_should_poll = False
    _attr_supported_color_modes = {ColorMode.ONOFF}
    _attr_color_mode = ColorMode.ONOFF
    _attr_has_entity_name = False

    def __init__(
        self,
        unique_id: str,
        name: str,
        sandbox_entity_id: str,
        bridge: OptionBMainBridge,
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
        """Forward turn_on as a standard light.turn_on service call."""
        await self._bridge.call_service(
            "light",
            "turn_on",
            target={"entity_id": [self._sandbox_entity_id]},
            service_data=kwargs,
        )
        self._is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Forward turn_off as a standard light.turn_off service call."""
        await self._bridge.call_service(
            "light",
            "turn_off",
            target={"entity_id": [self._sandbox_entity_id]},
            service_data=kwargs,
        )
        self._is_on = False
        self.async_write_ha_state()
