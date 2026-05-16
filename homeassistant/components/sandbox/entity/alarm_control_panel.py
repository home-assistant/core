"""Sandbox proxy for alarm_control_panel entities."""

from __future__ import annotations

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
)

from . import SandboxEntityDescription, SandboxEntityManager, SandboxProxyEntity


class SandboxAlarmControlPanelEntity(SandboxProxyEntity, AlarmControlPanelEntity):
    """Proxy for an alarm_control_panel entity in a sandbox."""

    def __init__(
        self,
        description: SandboxEntityDescription,
        manager: SandboxEntityManager,
    ) -> None:
        """Initialize the proxy alarm control panel entity."""
        super().__init__(description, manager)
        self._attr_supported_features = AlarmControlPanelEntityFeature(
            description.supported_features
        )
        caps = description.capabilities
        if code_format := caps.get("code_format"):
            self._attr_code_format = code_format
        if (code_arm_required := caps.get("code_arm_required")) is not None:
            self._attr_code_arm_required = code_arm_required

    @property
    def alarm_state(self) -> str | None:
        """Return the alarm state."""
        return self._state_cache.get("state")

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Forward alarm_disarm to sandbox."""
        await self._forward_method("async_alarm_disarm", code=code)

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Forward alarm_arm_home to sandbox."""
        await self._forward_method("async_alarm_arm_home", code=code)

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Forward alarm_arm_away to sandbox."""
        await self._forward_method("async_alarm_arm_away", code=code)

    async def async_alarm_arm_night(self, code: str | None = None) -> None:
        """Forward alarm_arm_night to sandbox."""
        await self._forward_method("async_alarm_arm_night", code=code)

    async def async_alarm_arm_vacation(self, code: str | None = None) -> None:
        """Forward alarm_arm_vacation to sandbox."""
        await self._forward_method("async_alarm_arm_vacation", code=code)

    async def async_alarm_trigger(self, code: str | None = None) -> None:
        """Forward alarm_trigger to sandbox."""
        await self._forward_method("async_alarm_trigger", code=code)
