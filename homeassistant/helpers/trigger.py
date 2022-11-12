"""Triggers."""
from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
import functools
import logging
from typing import TYPE_CHECKING, Any, Protocol, TypedDict, cast

import voluptuous as vol

from homeassistant.const import (
    CONF_ALIAS,
    CONF_ENABLED,
    CONF_ID,
    CONF_PLATFORM,
    CONF_VARIABLES,
)
from homeassistant.core import (
    CALLBACK_TYPE,
    Context,
    HassJob,
    HomeAssistant,
    callback,
    is_callback,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.loader import IntegrationNotFound, async_get_integration

from .typing import ConfigType, TemplateVarsType

if TYPE_CHECKING:
    from homeassistant.components.device_automation.trigger import (
        DeviceAutomationTriggerProtocol,
    )

_PLATFORM_ALIASES = {
    "device_automation": ("device",),
    "homeassistant": ("event", "numeric_state", "state", "time_pattern", "time"),
}

DATA_PLUGGABLE_ACTIONS = "pluggable_actions"


class TriggerActionType(Protocol):
    """Protocol type for trigger action callback."""

    async def __call__(
        self,
        run_variables: dict[str, Any],
        context: Context | None = None,
    ) -> None:
        """Define action callback type."""


class TriggerData(TypedDict):
    """Trigger data."""

    id: str
    idx: str
    alias: str | None


class TriggerInfo(TypedDict):
    """Information about trigger."""

    domain: str
    name: str
    home_assistant_start: bool
    variables: TemplateVarsType
    trigger_data: TriggerData


@dataclass
class PluggableActionEntry:
    """Holder to keep track of a single action and all plugs that is currently reacting."""

    action: TriggerActionType
    variables: dict[str, Any]
    removals: dict[PluggableAction, list[CALLBACK_TYPE]] = field(default_factory=dict)


@dataclass
class PluggableActionsEntry:
    """Holder to keep track of all plugs and actions for a given trigger."""

    plugs: list[PluggableAction] = field(default_factory=list)
    actions: dict[object, PluggableActionEntry] = field(default_factory=dict)


class PluggableAction:
    """A pluggable action handler."""

    def __init__(self, update: CALLBACK_TYPE | None = None) -> None:
        """Initialize."""
        self._update = update
        self._actions: dict[
            CALLBACK_TYPE,
            tuple[HassJob[..., Coroutine[Any, Any, None]], dict[str, Any]],
        ] = {}

    def __bool__(self) -> bool:
        """Return if we have something attached."""
        return bool(self._actions)

    @staticmethod
    def async_get_registry(hass: HomeAssistant) -> dict[tuple, PluggableActionsEntry]:
        """Return the pluggable actions registry."""

        if data := hass.data.get(DATA_PLUGGABLE_ACTIONS):
            return data  # type: ignore[no-any-return]
        data = defaultdict(PluggableActionsEntry)
        hass.data[DATA_PLUGGABLE_ACTIONS] = data
        return data

    @staticmethod
    def async_attach_all(
        hass: HomeAssistant,
        trigger: dict[str, str],
        action: TriggerActionType,
        variables: dict[str, Any],
    ) -> CALLBACK_TYPE:
        """Find all registered plugs of given trigger config."""

        key = tuple(sorted(trigger.items()))
        reg = PluggableAction.async_get_registry(hass)
        entries = reg[key]

        @callback
        def _remove() -> None:
            """Remove this action attachment, and disconnect all plugs."""
            entry = entries.actions.pop(_remove)
            for removal in entry.removals.values():
                for function in removal:
                    function()
            if not entries.actions and not entries.plugs:
                del reg[key]

        removals: dict[PluggableAction, list[CALLBACK_TYPE]] = {
            plug: [plug.async_attach(action, variables)] for plug in entries.plugs
        }
        entries.actions[_remove] = PluggableActionEntry(action, variables, removals)

        return _remove

    @callback
    def async_register(self, hass: HomeAssistant, trigger: ConfigType) -> CALLBACK_TYPE:
        """Register plug in the global plugs dictionary."""

        key = tuple(sorted(trigger.items()))
        reg = PluggableAction.async_get_registry(hass)
        entries = reg[key]

        for entry in entries.actions.values():
            functions = entry.removals.setdefault(self, [])
            functions.append(self.async_attach(entry.action, entry.variables))

        @callback
        def _remove() -> None:
            """Remove plug from registration, and make sure no action holds on to disconnection functions."""
            for entry in entries.actions.values():
                entry.removals.pop(self, None)
            entries.plugs.remove(self)
            if not entries.actions and not entries.plugs:
                del reg[key]

        entries.plugs.append(self)

        return _remove

    @callback
    def async_attach(
        self, action: TriggerActionType, variables: dict[str, Any]
    ) -> CALLBACK_TYPE:
        """Attach a device trigger."""

        @callback
        def _remove() -> None:
            del self._actions[_remove]
            if self._update:
                self._update()

        job = HassJob(action)

        self._actions[_remove] = (job, variables)
        if self._update:
            self._update()

        return _remove

    @callback
    def async_run(self, hass: HomeAssistant, context: Context | None = None) -> None:
        """Run all triggers."""
        for job, variables in self._actions.values():
            hass.async_run_hass_job(job, variables, context)


async def _async_get_trigger_platform(
    hass: HomeAssistant, config: ConfigType
) -> DeviceAutomationTriggerProtocol:
    platform_and_sub_type = config[CONF_PLATFORM].split(".")
    platform = platform_and_sub_type[0]
    for alias, triggers in _PLATFORM_ALIASES.items():
        if platform in triggers:
            platform = alias
            break
    try:
        integration = await async_get_integration(hass, platform)
    except IntegrationNotFound:
        raise vol.Invalid(f"Invalid platform '{platform}' specified") from None
    try:
        return integration.get_platform("trigger")
    except ImportError:
        raise vol.Invalid(
            f"Integration '{platform}' does not provide trigger support"
        ) from None


async def async_validate_trigger_config(
    hass: HomeAssistant, trigger_config: list[ConfigType]
) -> list[ConfigType]:
    """Validate triggers."""
    config = []
    for conf in trigger_config:
        platform = await _async_get_trigger_platform(hass, conf)
        if hasattr(platform, "async_validate_trigger_config"):
            conf = await platform.async_validate_trigger_config(hass, conf)
        else:
            conf = platform.TRIGGER_SCHEMA(conf)
        config.append(conf)
    return config


def _trigger_action_wrapper(
    hass: HomeAssistant, action: Callable, conf: ConfigType
) -> Callable:
    """Wrap trigger action with extra vars if configured.

    If action is a coroutine function, a coroutine function will be returned.
    If action is a callback, a callback will be returned.
    """
    if CONF_VARIABLES not in conf:
        return action

    # Check for partials to properly determine if coroutine function
    check_func = action
    while isinstance(check_func, functools.partial):
        check_func = check_func.func

    wrapper_func: Callable[..., None] | Callable[..., Coroutine[Any, Any, None]]
    if asyncio.iscoroutinefunction(check_func):
        async_action = cast(Callable[..., Coroutine[Any, Any, None]], action)

        @functools.wraps(async_action)
        async def async_with_vars(
            run_variables: dict[str, Any], context: Context | None = None
        ) -> None:
            """Wrap action with extra vars."""
            trigger_variables = conf[CONF_VARIABLES]
            run_variables.update(trigger_variables.async_render(hass, run_variables))
            await action(run_variables, context)

        wrapper_func = async_with_vars

    else:

        @functools.wraps(action)
        async def with_vars(
            run_variables: dict[str, Any], context: Context | None = None
        ) -> None:
            """Wrap action with extra vars."""
            trigger_variables = conf[CONF_VARIABLES]
            run_variables.update(trigger_variables.async_render(hass, run_variables))
            action(run_variables, context)

        if is_callback(check_func):
            with_vars = callback(with_vars)

        wrapper_func = with_vars

    return wrapper_func


async def async_initialize_triggers(
    hass: HomeAssistant,
    trigger_config: list[ConfigType],
    action: Callable,
    domain: str,
    name: str,
    log_cb: Callable,
    home_assistant_start: bool = False,
    variables: TemplateVarsType = None,
) -> CALLBACK_TYPE | None:
    """Initialize triggers."""
    triggers = []
    for idx, conf in enumerate(trigger_config):
        # Skip triggers that are not enabled
        if not conf.get(CONF_ENABLED, True):
            continue

        platform = await _async_get_trigger_platform(hass, conf)
        trigger_id = conf.get(CONF_ID, f"{idx}")
        trigger_idx = f"{idx}"
        trigger_alias = conf.get(CONF_ALIAS)
        trigger_data = TriggerData(id=trigger_id, idx=trigger_idx, alias=trigger_alias)
        info = TriggerInfo(
            domain=domain,
            name=name,
            home_assistant_start=home_assistant_start,
            variables=variables,
            trigger_data=trigger_data,
        )

        triggers.append(
            platform.async_attach_trigger(
                hass, conf, _trigger_action_wrapper(hass, action, conf), info
            )
        )

    attach_results = await asyncio.gather(*triggers, return_exceptions=True)
    removes: list[Callable[[], None]] = []

    for result in attach_results:
        if isinstance(result, HomeAssistantError):
            log_cb(logging.ERROR, f"Got error '{result}' when setting up triggers for")
        elif isinstance(result, Exception):
            log_cb(logging.ERROR, "Error setting up trigger", exc_info=result)
        elif result is None:
            log_cb(
                logging.ERROR, "Unknown error while setting up trigger (empty result)"
            )
        else:
            removes.append(result)

    if not removes:
        return None

    log_cb(logging.INFO, "Initialized trigger")

    @callback
    def remove_triggers() -> None:
        """Remove triggers."""
        for remove in removes:
            remove()

    return remove_triggers
