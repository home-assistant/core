"""Sandbox proxy for number entities."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode

from . import SandboxEntityDescription, SandboxEntityManager, SandboxProxyEntity


class SandboxNumberEntity(SandboxProxyEntity, NumberEntity):
    """Proxy for a number entity in a sandbox."""

    def __init__(
        self,
        description: SandboxEntityDescription,
        manager: SandboxEntityManager,
    ) -> None:
        """Initialize the proxy number entity."""
        super().__init__(description, manager)
        caps = description.capabilities
        if (min_val := caps.get("native_min_value")) is not None:
            self._attr_native_min_value = min_val
        if (max_val := caps.get("native_max_value")) is not None:
            self._attr_native_max_value = max_val
        if (step := caps.get("native_step")) is not None:
            self._attr_native_step = step
        if unit := caps.get("native_unit_of_measurement"):
            self._attr_native_unit_of_measurement = unit
        if mode := caps.get("mode"):
            self._attr_mode = NumberMode(mode)

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        val = self._state_cache.get("state")
        if val is None:
            return None
        return float(val)

    async def async_set_native_value(self, value: float) -> None:
        """Forward set_native_value to sandbox."""
        await self._forward_method("async_set_native_value", value=value)
