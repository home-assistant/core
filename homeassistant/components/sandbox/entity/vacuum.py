"""Sandbox proxy for vacuum entities."""

from __future__ import annotations

from typing import Any

from homeassistant.components.vacuum import StateVacuumEntity, VacuumEntityFeature

from . import SandboxEntityDescription, SandboxEntityManager, SandboxProxyEntity


class SandboxVacuumEntity(SandboxProxyEntity, StateVacuumEntity):
    """Proxy for a vacuum entity in a sandbox."""

    def __init__(
        self,
        description: SandboxEntityDescription,
        manager: SandboxEntityManager,
    ) -> None:
        """Initialize the proxy vacuum entity."""
        super().__init__(description, manager)
        self._attr_supported_features = VacuumEntityFeature(
            description.supported_features
        )
        if fan_speed_list := description.capabilities.get("fan_speed_list"):
            self._attr_fan_speed_list = fan_speed_list

    @property
    def activity(self) -> str | None:
        """Return the current vacuum activity."""
        return self._state_cache.get("activity")

    @property
    def battery_level(self) -> int | None:
        """Return the battery level."""
        return self._state_cache.get("battery_level")

    @property
    def fan_speed(self) -> str | None:
        """Return the current fan speed."""
        return self._state_cache.get("fan_speed")

    async def async_start(self) -> None:
        """Forward start to sandbox."""
        await self._forward_method("async_start")

    async def async_pause(self) -> None:
        """Forward pause to sandbox."""
        await self._forward_method("async_pause")

    async def async_stop(self, **kwargs: Any) -> None:
        """Forward stop to sandbox."""
        await self._forward_method("async_stop", **kwargs)

    async def async_return_to_base(self, **kwargs: Any) -> None:
        """Forward return_to_base to sandbox."""
        await self._forward_method("async_return_to_base", **kwargs)

    async def async_clean_spot(self, **kwargs: Any) -> None:
        """Forward clean_spot to sandbox."""
        await self._forward_method("async_clean_spot", **kwargs)

    async def async_locate(self, **kwargs: Any) -> None:
        """Forward locate to sandbox."""
        await self._forward_method("async_locate", **kwargs)

    async def async_set_fan_speed(self, fan_speed: str, **kwargs: Any) -> None:
        """Forward set_fan_speed to sandbox."""
        await self._forward_method("async_set_fan_speed", fan_speed=fan_speed, **kwargs)

    async def async_send_command(self, command: str, params: dict[str, Any] | list[Any] | None = None, **kwargs: Any) -> None:
        """Forward send_command to sandbox."""
        await self._forward_method("async_send_command", command=command, params=params, **kwargs)
