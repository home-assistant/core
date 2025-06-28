"""Triggers."""

from __future__ import annotations

import abc
import asyncio
from collections import defaultdict
from collections.abc import Callable, Coroutine, Iterable
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
from homeassistant.exceptions import HomeAssistantError, TemplateError
from homeassistant.loader import (
    Integration,
    IntegrationNotFound,
    async_get_integration,
    async_get_integrations,
)
from homeassistant.util.async_ import create_eager_task
from homeassistant.util.hass_dict import HassKey
from homeassistant.util.yaml import load_yaml_dict
from homeassistant.util.yaml.loader import JSON_TYPE

from . import config_validation as cv
from .integration_platform import async_process_integration_platforms
from .template import Template
from .typing import ConfigType, TemplateVarsType

_LOGGER = logging.getLogger(__name__)

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

TRIGGER_DESCRIPTION_CACHE: HassKey[dict[str, dict[str, Any] | None]] = HassKey(
    "trigger_description_cache"
)
TRIGGER_PLATFORM_SUBSCRIPTIONS: HassKey[
    list[Callable[[set[str]], Coroutine[Any, Any, None]]]
] = HassKey("trigger_platform_subscriptions")
TRIGGERS: HassKey[dict[str, str]] = HassKey("triggers")


# Basic schemas to sanity check the trigger descriptions,
# full validation is done by hassfest.triggers
_FIELD_SCHEMA = vol.Schema(
    {},
    extra=vol.ALLOW_EXTRA,
)

_TRIGGER_SCHEMA = vol.Schema(
    {
        vol.Optional("fields"): vol.Schema({str: _FIELD_SCHEMA}),
    },
    extra=vol.ALLOW_EXTRA,
)


def starts_with_dot(key: str) -> str:
    """Check if key starts with dot."""
    if not key.startswith("."):
        raise vol.Invalid("Key does not start with .")
    return key


_TRIGGERS_SCHEMA = vol.Schema(
    {
        vol.Remove(vol.All(str, starts_with_dot)): object,
        cv.slug: vol.Any(None, _TRIGGER_SCHEMA),
    }
)


async def async_setup(hass: HomeAssistant) -> None:
    """Set up the trigger helper."""
    hass.data[TRIGGER_DESCRIPTION_CACHE] = {}
    hass.data[TRIGGER_PLATFORM_SUBSCRIPTIONS] = []
    hass.data[TRIGGERS] = {}
    await async_process_integration_platforms(
        hass, "trigger", _register_trigger_platform, wait_for_platforms=True
    )


@callback
def async_subscribe_platform_events(
    hass: HomeAssistant,
    on_event: Callable[[set[str]], Coroutine[Any, Any, None]],
) -> Callable[[], None]:
    """Subscribe to trigger platform events."""
    trigger_platform_event_subscriptions = hass.data[TRIGGER_PLATFORM_SUBSCRIPTIONS]

    def remove_subscription() -> None:
        trigger_platform_event_subscriptions.remove(on_event)

    trigger_platform_event_subscriptions.append(on_event)
    return remove_subscription


async def _register_trigger_platform(
    hass: HomeAssistant, integration_domain: str, platform: TriggerProtocol
) -> None:
    """Register a trigger platform."""

    new_triggers: set[str] = set()

    if hasattr(platform, "async_get_triggers"):
        for trigger_key in await platform.async_get_triggers(hass):
            hass.data[TRIGGERS][trigger_key] = integration_domain
            new_triggers.add(trigger_key)
    elif hasattr(platform, "async_validate_trigger_config") or hasattr(
        platform, "TRIGGER_SCHEMA"
    ):
        hass.data[TRIGGERS][integration_domain] = integration_domain
        new_triggers.add(integration_domain)
    else:
        _LOGGER.debug(
            "Integration %s does not provide trigger support, skipping",
            integration_domain,
        )
        return

    tasks: list[asyncio.Task[None]] = [
        create_eager_task(listener(new_triggers))
        for listener in hass.data[TRIGGER_PLATFORM_SUBSCRIPTIONS]
    ]
    await asyncio.gather(*tasks)


class Trigger(abc.ABC):
    """Trigger class."""

    def __init__(self, hass: HomeAssistant, config: ConfigType) -> None:
        """Initialize trigger."""

    @classmethod
    @abc.abstractmethod
    async def async_validate_trigger_config(
        cls, hass: HomeAssistant, config: ConfigType
    ) -> ConfigType:
        """Validate config."""

    @abc.abstractmethod
    async def async_attach_trigger(
        self,
        action: TriggerActionType,
        trigger_info: TriggerInfo,
    ) -> CALLBACK_TYPE:
        """Attach a trigger."""


class TriggerProtocol(Protocol):
    """Define the format of trigger modules.

    New implementations should only implement async_get_triggers.
    """

    async def async_get_triggers(self, hass: HomeAssistant) -> dict[str, type[Trigger]]:
        """Return the triggers provided by this integration."""

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
    trigger_key: str = config[CONF_PLATFORM]
    platform_and_sub_type = trigger_key.split(".")
    platform = platform_and_sub_type[0]
    platform = _PLATFORM_ALIASES.get(platform, platform)
    try:
        integration = await async_get_integration(hass, platform)
    except IntegrationNotFound:
        raise vol.Invalid(f"Invalid trigger '{trigger_key}' specified") from None
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
        if hasattr(platform, "async_get_triggers"):
            trigger_descriptors = await platform.async_get_triggers(hass)
            trigger_key: str = conf[CONF_PLATFORM]
            if not (trigger := trigger_descriptors.get(trigger_key)):
                raise vol.Invalid(f"Invalid trigger '{trigger_key}' specified")
            conf = await trigger.async_validate_trigger_config(hass, conf)
        elif hasattr(platform, "async_validate_trigger_config"):
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

    wrapper_func: Callable[..., Any] | Callable[..., Coroutine[Any, Any, Any]]
    if asyncio.iscoroutinefunction(check_func):
        async_action = cast(Callable[..., Coroutine[Any, Any, Any]], action)

        @functools.wraps(async_action)
        async def async_with_vars(
            run_variables: dict[str, Any], context: Context | None = None
        ) -> Any:
            """Wrap action with extra vars."""
            trigger_variables = conf[CONF_VARIABLES]
            run_variables.update(trigger_variables.async_render(hass, run_variables))
            return await action(run_variables, context)

        wrapper_func = async_with_vars

    else:

        @functools.wraps(action)
        async def with_vars(
            run_variables: dict[str, Any], context: Context | None = None
        ) -> Any:
            """Wrap action with extra vars."""
            trigger_variables = conf[CONF_VARIABLES]
            run_variables.update(trigger_variables.async_render(hass, run_variables))
            return action(run_variables, context)

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

        action_wrapper = _trigger_action_wrapper(hass, action, conf)
        if hasattr(platform, "async_get_triggers"):
            trigger_descriptors = await platform.async_get_triggers(hass)
            trigger = trigger_descriptors[conf[CONF_PLATFORM]](hass, conf)
            coro = trigger.async_attach_trigger(action_wrapper, info)
        else:
            coro = platform.async_attach_trigger(hass, conf, action_wrapper, info)

        triggers.append(create_eager_task(coro))

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


def _load_triggers_file(hass: HomeAssistant, integration: Integration) -> JSON_TYPE:
    """Load triggers file for an integration."""
    try:
        return cast(
            JSON_TYPE,
            _TRIGGERS_SCHEMA(
                load_yaml_dict(str(integration.file_path / "triggers.yaml"))
            ),
        )
    except FileNotFoundError:
        _LOGGER.warning(
            "Unable to find triggers.yaml for the %s integration", integration.domain
        )
        return {}
    except (HomeAssistantError, vol.Invalid) as ex:
        _LOGGER.warning(
            "Unable to parse triggers.yaml for the %s integration: %s",
            integration.domain,
            ex,
        )
        return {}


def _load_triggers_files(
    hass: HomeAssistant, integrations: Iterable[Integration]
) -> dict[str, JSON_TYPE]:
    """Load trigger files for multiple integrations."""
    return {
        integration.domain: _load_triggers_file(hass, integration)
        for integration in integrations
    }


async def async_get_all_descriptions(
    hass: HomeAssistant,
) -> dict[str, dict[str, Any] | None]:
    """Return descriptions (i.e. user documentation) for all triggers."""
    descriptions_cache = hass.data[TRIGGER_DESCRIPTION_CACHE]

    triggers = hass.data[TRIGGERS]
    # See if there are new triggers not seen before.
    # Any trigger that we saw before already has an entry in description_cache.
    all_triggers = set(triggers)
    previous_all_triggers = set(descriptions_cache)
    # If the triggers are the same, we can return the cache
    if previous_all_triggers == all_triggers:
        return descriptions_cache

    # Files we loaded for missing descriptions
    new_triggers_descriptions: dict[str, JSON_TYPE] = {}
    # We try to avoid making a copy in the event the cache is good,
    # but now we must make a copy in case new triggers get added
    # while we are loading the missing ones so we do not
    # add the new ones to the cache without their descriptions
    triggers = triggers.copy()

    if missing_triggers := all_triggers.difference(descriptions_cache):
        domains_with_missing_triggers = {
            triggers[missing_trigger] for missing_trigger in missing_triggers
        }
        ints_or_excs = await async_get_integrations(hass, domains_with_missing_triggers)
        integrations: list[Integration] = []
        for domain, int_or_exc in ints_or_excs.items():
            if type(int_or_exc) is Integration and int_or_exc.has_triggers:
                integrations.append(int_or_exc)
                continue
            if TYPE_CHECKING:
                assert isinstance(int_or_exc, Exception)
            _LOGGER.debug(
                "Failed to load triggers.yaml for integration: %s",
                domain,
                exc_info=int_or_exc,
            )

        if integrations:
            new_triggers_descriptions = await hass.async_add_executor_job(
                _load_triggers_files, hass, integrations
            )

    # Make a copy of the old cache and add missing descriptions to it
    new_descriptions_cache = descriptions_cache.copy()
    for missing_trigger in missing_triggers:
        domain = triggers[missing_trigger]

        if (
            yaml_description := new_triggers_descriptions.get(domain, {}).get(  # type: ignore[union-attr]
                missing_trigger
            )
        ) is None:
            _LOGGER.debug(
                "No trigger descriptions found for trigger %s, skipping",
                missing_trigger,
            )
            new_descriptions_cache[missing_trigger] = None
            continue

        description = {"fields": yaml_description.get("fields", {})}

        new_descriptions_cache[missing_trigger] = description

    hass.data[TRIGGER_DESCRIPTION_CACHE] = new_descriptions_cache
    return new_descriptions_cache
