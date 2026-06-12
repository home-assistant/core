"""Sandbox proxy for ``alarm_control_panel`` entities."""

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
    CodeFormat,
)

from . import SandboxProxyEntity


# pylint: disable-next=home-assistant-enforce-class-module
class SandboxAlarmControlPanelEntity(SandboxProxyEntity, AlarmControlPanelEntity):
    """Proxy for an ``alarm_control_panel`` entity in a sandbox."""

    _features_flag = AlarmControlPanelEntityFeature

    @property
    def alarm_state(self) -> AlarmControlPanelState | None:
        """Return the cached alarm state."""
        value = self._state_cache.get("state")
        if value is None:
            return None
        try:
            return AlarmControlPanelState(value)
        except ValueError:
            return None

    @property
    def code_format(self) -> CodeFormat | None:
        """Return the configured code format."""
        value = self.description.capabilities.get("code_format")
        if value is None:
            return None
        try:
            return CodeFormat(value)
        except ValueError:
            return None

    @property
    def changed_by(self) -> str | None:
        """Return the cached changed_by user."""
        return self._state_cache.get("changed_by")

    @property
    def code_arm_required(self) -> bool:
        """Mirror the sandbox-side requirement flag."""
        return bool(self.description.capabilities.get("code_arm_required", True))

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Forward disarm as ``alarm_control_panel.alarm_disarm``."""
        await self._call_service("alarm_disarm", code=code)

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Forward arm_home as ``alarm_control_panel.alarm_arm_home``."""
        await self._call_service("alarm_arm_home", code=code)

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Forward arm_away as ``alarm_control_panel.alarm_arm_away``."""
        await self._call_service("alarm_arm_away", code=code)

    async def async_alarm_arm_night(self, code: str | None = None) -> None:
        """Forward arm_night as ``alarm_control_panel.alarm_arm_night``."""
        await self._call_service("alarm_arm_night", code=code)

    async def async_alarm_arm_vacation(self, code: str | None = None) -> None:
        """Forward arm_vacation as ``alarm_control_panel.alarm_arm_vacation``."""
        await self._call_service("alarm_arm_vacation", code=code)

    async def async_alarm_trigger(self, code: str | None = None) -> None:
        """Forward trigger as ``alarm_control_panel.alarm_trigger``."""
        await self._call_service("alarm_trigger", code=code)

    async def async_alarm_arm_custom_bypass(self, code: str | None = None) -> None:
        """Forward arm_custom_bypass."""
        await self._call_service("alarm_arm_custom_bypass", code=code)
