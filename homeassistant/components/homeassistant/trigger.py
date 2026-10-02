"""Home Assistant trigger dispatcher."""

from typing import cast, override

import probatio

from homeassistant.const import CONF_OPTIONS, CONF_PLATFORM
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers import system_state
from homeassistant.helpers.importlib import async_import_module
from homeassistant.helpers.trigger import (
    Trigger,
    TriggerActionRunner,
    TriggerActionType,
    TriggerInfo,
    TriggerNotTriggeredReporter,
    TriggerProtocol,
)
from homeassistant.helpers.typing import ConfigType

_SYSTEM_STATE_TRIGGER_SCHEMA = probatio.Schema(
    {probatio.Required(CONF_OPTIONS, default=dict): {}}
)


async def _async_get_trigger_platform(
    hass: HomeAssistant, platform_name: str
) -> TriggerProtocol:
    """Get trigger platform from cache or import it."""
    platform = await async_import_module(
        hass, f"homeassistant.components.homeassistant.triggers.{platform_name}"
    )
    return cast(TriggerProtocol, platform)


async def async_validate_trigger_config(
    hass: HomeAssistant, config: ConfigType
) -> ConfigType:
    """Validate config."""
    platform = await _async_get_trigger_platform(hass, config[CONF_PLATFORM])
    if hasattr(platform, "async_validate_trigger_config"):
        return await platform.async_validate_trigger_config(hass, config)

    return platform.TRIGGER_SCHEMA(config)  # type: ignore[no-any-return]


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    """Attach trigger of specified platform."""
    platform = await _async_get_trigger_platform(hass, config[CONF_PLATFORM])
    return await platform.async_attach_trigger(hass, config, action, trigger_info)


class _SystemStateTrigger(Trigger):
    """Base class for triggers that fire when a system state flag gets set."""

    _description: str

    @override
    @classmethod
    async def async_validate_config(
        cls, hass: HomeAssistant, config: ConfigType
    ) -> ConfigType:
        """Validate config."""
        return cast(ConfigType, _SYSTEM_STATE_TRIGGER_SCHEMA(config))

    def _is_set(self, state: system_state.SystemState) -> bool:
        """Return if the flag this trigger watches is set."""
        raise NotImplementedError

    def _trigger_payload(self, state: system_state.SystemState) -> dict[str, object]:
        """Return the trigger payload."""
        return {}

    @override
    async def async_attach_runner(
        self,
        run_action: TriggerActionRunner,
        did_not_trigger: TriggerNotTriggeredReporter | None = None,
    ) -> CALLBACK_TYPE:
        """Attach the trigger to an action runner."""
        was_set = self._is_set(system_state.async_get(self._hass))

        @callback
        def check_state(state: system_state.SystemState) -> None:
            nonlocal was_set
            is_set = self._is_set(state)
            if is_set and not was_set:
                run_action(self._trigger_payload(state), self._description)
            was_set = is_set

        return system_state.async_subscribe(self._hass, check_state)


class RestartRequiredTrigger(_SystemStateTrigger):
    """Trigger that fires when Home Assistant needs a restart."""

    _description = "Home Assistant restart required"

    @override
    def _is_set(self, state: system_state.SystemState) -> bool:
        """Return if a restart of Home Assistant is required."""
        return state.home_assistant_restart_required

    @override
    def _trigger_payload(self, state: system_state.SystemState) -> dict[str, object]:
        """Return the integrations that asked for the restart."""
        return {"sources": sorted(state.home_assistant_restart_sources)}


class HostRebootRequiredTrigger(_SystemStateTrigger):
    """Trigger that fires when the host needs a reboot."""

    _description = "host reboot required"

    @override
    def _is_set(self, state: system_state.SystemState) -> bool:
        """Return if a reboot of the host is required."""
        return state.host_reboot_required


TRIGGERS: dict[str, type[Trigger]] = {
    "host_reboot_required": HostRebootRequiredTrigger,
    "restart_required": RestartRequiredTrigger,
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for Home Assistant."""
    return TRIGGERS
