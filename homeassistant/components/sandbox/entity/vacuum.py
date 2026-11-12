"""Sandbox proxy for ``vacuum`` entities."""

from typing import Any, override

from homeassistant.components.vacuum import (
    ATTR_FAN_SPEED,
    ATTR_FAN_SPEED_LIST,
    Segment,
    StateVacuumEntity,
    VacuumActivity,
    VacuumEntityFeature,
)

from . import SandboxProxyEntity


def _segment_from_dict(data: dict[str, Any]) -> Segment:
    """Rebuild a :class:`Segment` dataclass from its serialised dict."""
    return Segment(id=data["id"], name=data["name"], group=data.get("group"))


# pylint: disable-next=home-assistant-enforce-class-module
class SandboxVacuumEntity(SandboxProxyEntity, StateVacuumEntity):
    """Proxy for a ``vacuum`` entity in a sandbox."""

    _features_flag = VacuumEntityFeature

    @property
    @override
    def activity(self) -> VacuumActivity | None:
        """Return the cached vacuum activity."""
        value = self._state_cache.get("state")
        if value is None or value == "unavailable":
            return None
        try:
            return VacuumActivity(value)
        except ValueError:
            return None

    @property
    @override
    def fan_speed(self) -> str | None:
        """Return the cached fan speed."""
        return self._state_cache.get(ATTR_FAN_SPEED)

    @property
    @override
    def fan_speed_list(self) -> list[str]:
        """Return the configured fan speed list."""
        return list(self.description.capabilities.get(ATTR_FAN_SPEED_LIST) or [])

    @override
    async def async_start(self) -> None:
        """Forward start."""
        await self._call_service("start")

    @override
    async def async_pause(self) -> None:
        """Forward pause."""
        await self._call_service("pause")

    @override
    async def async_stop(self, **kwargs: Any) -> None:
        """Forward stop."""
        await self._call_service("stop", **kwargs)

    @override
    async def async_return_to_base(self, **kwargs: Any) -> None:
        """Forward return_to_base."""
        await self._call_service("return_to_base", **kwargs)

    @override
    async def async_clean_spot(self, **kwargs: Any) -> None:
        """Forward clean_spot."""
        await self._call_service("clean_spot", **kwargs)

    @override
    async def async_locate(self, **kwargs: Any) -> None:
        """Forward locate."""
        await self._call_service("locate", **kwargs)

    @override
    async def async_set_fan_speed(self, fan_speed: str, **kwargs: Any) -> None:
        """Forward set_fan_speed."""
        await self._call_service("set_fan_speed", fan_speed=fan_speed, **kwargs)

    @override
    async def async_send_command(
        self,
        command: str,
        params: dict[str, Any] | list[Any] | None = None,
        **kwargs: Any,
    ) -> None:
        """Forward send_command."""
        payload: dict[str, Any] = {"command": command, **kwargs}
        if params is not None:
            payload["params"] = params
        await self._call_service("send_command", **payload)

    @override
    async def async_get_segments(self) -> list[Segment]:
        """Return the cleanable segments via ``EntityQuery``."""
        response = await self._entity_query("async_get_segments")
        return [_segment_from_dict(segment) for segment in response or []]
