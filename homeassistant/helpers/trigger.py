"""Triggers."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
import functools
import logging
from typing import Any, Protocol, TypedDict, cast

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
from homeassistant.exceptions import HomeAssistantError, TemplateError
from homeassistant.loader import IntegrationNotFound, async_get_integration
from homeassistant.util.async_ import create_eager_task
from homeassistant.util.hass_dict import HassKey

from .template import Template
from .typing import ConfigType, TemplateVarsType

_PLATFORM_ALIASES = {
    "device": "device_automation",
    "event": "homeassistant",
    "numeric_state": "homeassistant",
    "state": "homeassistant",
    "time_pattern": "homeassistant",
    "time": "homeassistant",
}

DATA_PLUGGABLE_ACTIONS: HassKey[defaultdict[tuple, PluggableActionsEntry]] = HassKey(
    "pluggable_actions"
)


class TriggerProtocol(Protocol):
    """Define the format of trigger modules.

    Each module must define either TRIGGER_SCHEMA or async_validate_trigger_config.
    """

    TRIGGER_SCHEMA: vol.Schema

    async def async_validate_trigger_config(
        self, hass: HomeAssistant, config: ConfigType
    ) -> ConfigType:
        """Validate config."""

    async def async_attach_trigger(
        self,
        hass: HomeAssistant,
        config: ConfigType,
        action: TriggerActionType,
        trigger_info: TriggerInfo,
    ) -> CALLBACK_TYPE:
        """Attach a trigger."""


class TriggerActionType(Protocol):
    """Protocol type for trigger action callback."""

    async def __call__(
        self,
        run_variables: dict[str, Any],
        context: Context | None = None,
    ) -> Any:
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


@dataclass(slots=True)
class PluggableActionsEntry:
    """Holder to keep track of all plugs and actions for a given trigger."""

    plugs: set[PluggableAction] = field(default_factory=set)
    actions: dict[
        object,
        tuple[
            HassJob[[dict[str, Any], Context | None], Coroutine[Any, Any, None]],
            dict[str, Any],
        ],
    ] = field(default_factory=dict)


class PluggableAction:
    """A pluggable action handler."""

    _entry: PluggableActionsEntry | None = None

    def __init__(self, update: CALLBACK_TYPE | None = None) -> None:
        """Initialize a pluggable action.

        :param update: callback triggered whenever triggers are attached or removed.
        """
        self._update = update

    def __bool__(self) -> bool:
        """Return if we have something attached."""
        return bool(self._entry and self._entry.actions)

    @callback
    def async_run_update(self) -> None:
        """Run update function if one exists."""
        if self._update:
            self._update()

    @staticmethod
    @callback
    def async_get_registry(hass: HomeAssistant) -> dict[tuple, PluggableActionsEntry]:
        """Return the pluggable actions registry."""
        if data := hass.data.get(DATA_PLUGGABLE_ACTIONS):
            return data
        data = hass.data[DATA_PLUGGABLE_ACTIONS] = defaultdict(PluggableActionsEntry)
        return data

    @staticmethod
    @callback
    def async_attach_trigger(
        hass: HomeAssistant,
        trigger: dict[str, str],
        action: TriggerActionType,
        variables: dict[str, Any],
    ) -> CALLBACK_TYPE:
        """Attach an action to a trigger entry.

        Existing or future plugs registered will be attached.
        """
        reg = PluggableAction.async_get_registry(hass)
        key = tuple(sorted(trigger.items()))
        entry = reg[key]

        def _update() -> None:
            for plug in entry.plugs:
                plug.async_run_update()

        @callback
        def _remove() -> None:
            """Remove this action attachment, and disconnect all plugs."""
            del entry.actions[_remove]
            _update()
            if not entry.actions and not entry.plugs:
                del reg[key]

        job = HassJob(action, f"trigger {trigger} {variables}")
        entry.actions[_remove] = (job, variables)
        _update()

        return _remove

    @callback
    def async_register(
        self, hass: HomeAssistant, trigger: dict[str, str]
    ) -> CALLBACK_TYPE:
        """Register plug in the global plugs dictionary."""

        reg = PluggableAction.async_get_registry(hass)
        key = tuple(sorted(trigger.items()))
        self._entry = reg[key]
        self._entry.plugs.add(self)

        @callback
        def _remove() -> None:
            """Remove plug from registration.

            Clean up entry if there are no actions or plugs registered.
            """
            assert self._entry
            self._entry.plugs.remove(self)
            if not self._entry.actions and not self._entry.plugs:
                del reg[key]
            self._entry = None

        return _remove

    async def async_run(
        self, hass: HomeAssistant, context: Context | None = None
    ) -> None:
        """Run all actions."""
        assert self._entry
        for job, variables in self._entry.actions.values():
            task = hass.async_run_hass_job(job, variables, context)
            if task:
                await task


async def _async_get_trigger_platform(
    hass: HomeAssistant, config: ConfigType
) -> TriggerProtocol:
    platform_and_sub_type = config[CONF_PLATFORM].split(".")
    platform = platform_and_sub_type[0]
    platform = _PLATFORM_ALIASES.get(platform, platform)
    try:
        integration = await async_get_integration(hass, platform)
    except IntegrationNotFound:
        raise vol.Invalid(f"Invalid trigger '{platform}' specified") from None
    try:
        return await integration.async_get_platform("trigger")
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
    triggers: list[asyncio.Task[CALLBACK_TYPE]] = []
    for idx, conf in enumerate(trigger_config):
        # Skip triggers that are not enabled
        if CONF_ENABLED in conf:
            enabled = conf[CONF_ENABLED]
            if isinstance(enabled, Template):
                try:
                    enabled = enabled.async_render(variables, limited=True)
                except TemplateError as err:
                    log_cb(logging.ERROR, f"Error rendering enabled template: {err}")
                    continue
            if not enabled:
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
            create_eager_task(
                platform.async_attach_trigger(
                    hass, conf, _trigger_action_wrapper(hass, action, conf), info
                )
            )
        )

    attach_results = await asyncio.gather(*triggers, return_exceptions=True)
    removes: list[Callable[[], None]] = []

    for result in attach_results:
        if isinstance(result, HomeAssistantError):
            log_cb(logging.ERROR, f"Got error '{result}' when setting up triggers for")
        elif isinstance(result, Exception):
            log_cb(logging.ERROR, "Error setting up trigger", exc_info=result)
        elif isinstance(result, BaseException):
            raise result from None
        elif result is None:
            log_cb(  # type: ignore[unreachable]
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
