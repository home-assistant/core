"""Triggers."""

import asyncio
from collections import defaultdict
from collections.abc import Callable, Coroutine
from contextvars import copy_context
from dataclasses import dataclass, field
import functools
import inspect
import logging
from typing import Any, Literal, Protocol, TypedDict, cast

import probatio

from homeassistant.const import (
    CONF_ALIAS,
    CONF_AT,
    CONF_DEVICE_ID,
    CONF_ENABLED,
    CONF_ENTITY_ID,
    CONF_EVENT_DATA,
    CONF_ID,
    CONF_OPTIONS,
    CONF_PLATFORM,
    CONF_TARGET,
    CONF_VARIABLES,
    CONF_ZONE,
)
from homeassistant.core import (
    CALLBACK_TYPE,
    Context,
    HassJob,
    HassJobType,
    HomeAssistant,
    callback,
    get_hassjob_callable_job_type,
    is_callback,
    valid_entity_id,
)
from homeassistant.exceptions import HomeAssistantError, TemplateError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.automation import (
    get_absolute_description_key,
    get_relative_description_key,
    move_options_fields_to_top_level,
)
from homeassistant.helpers.frame import report_usage
from homeassistant.helpers.integration_platform import (
    async_process_integration_platforms,
)
from homeassistant.helpers.template import Template
from homeassistant.helpers.typing import (
    UNDEFINED,
    ConfigType,
    TemplateVarsType,
    UndefinedType,
)
from homeassistant.loader import IntegrationNotFound, async_get_integration
from homeassistant.util.async_ import create_eager_task
from homeassistant.util.hass_dict import HassKey

from .descriptions import (
    TRIGGER_DESCRIPTION_CACHE,
    async_get_all_descriptions,
    starts_with_dot,
)
from .entity_trigger import (
    ATTR_BEHAVIOR,
    BEHAVIOR_ALL,
    BEHAVIOR_EACH,
    BEHAVIOR_FIRST,
    ENTITY_STATE_TRIGGER_SCHEMA,
    ENTITY_STATE_TRIGGER_SCHEMA_WITH_BEHAVIOR,
    NUMERICAL_ATTRIBUTE_CHANGED_TRIGGER_SCHEMA,
    NUMERICAL_ATTRIBUTE_CROSSED_THRESHOLD_SCHEMA,
    EntityNumericalStateChangedTriggerBase,
    EntityNumericalStateChangedTriggerWithUnitBase,
    EntityNumericalStateCrossedThresholdTriggerBase,
    EntityNumericalStateCrossedThresholdTriggerWithUnitBase,
    EntityNumericalStateTriggerBase,
    EntityNumericalStateTriggerWithUnitBase,
    EntityOriginStateTriggerBase,
    EntityTargetStateTriggerBase,
    EntityTransitionTriggerBase,
    EntityTriggerBase,
    NotTriggeredReasonReporter,
    StatelessEntityTriggerBase,
    make_entity_numerical_state_changed_trigger,
    make_entity_numerical_state_changed_with_unit_trigger,
    make_entity_numerical_state_crossed_threshold_trigger,
    make_entity_numerical_state_crossed_threshold_with_unit_trigger,
    make_entity_origin_state_trigger,
    make_entity_target_state_trigger,
    make_entity_transition_trigger,
    make_numerical_state_changed_with_unit_schema,
)
from .models import (
    TRIGGERS,
    NotTriggeredInfo,
    Trigger,
    TriggerAction,
    TriggerActionPayloadBuilder,
    TriggerActionRunner,
    TriggerConfig,
    TriggerNotTriggeredReporter,
)

__all__ = [
    "ATTR_BEHAVIOR",
    "BEHAVIOR_ALL",
    "BEHAVIOR_EACH",
    "BEHAVIOR_FIRST",
    "DATA_PLUGGABLE_ACTIONS",
    "ENTITY_STATE_TRIGGER_SCHEMA",
    "ENTITY_STATE_TRIGGER_SCHEMA_WITH_BEHAVIOR",
    "NUMERICAL_ATTRIBUTE_CHANGED_TRIGGER_SCHEMA",
    "NUMERICAL_ATTRIBUTE_CROSSED_THRESHOLD_SCHEMA",
    "TRIGGERS",
    "TRIGGER_DESCRIPTION_CACHE",
    "TRIGGER_PLATFORM_SUBSCRIPTIONS",
    "EntityNumericalStateChangedTriggerBase",
    "EntityNumericalStateChangedTriggerWithUnitBase",
    "EntityNumericalStateCrossedThresholdTriggerBase",
    "EntityNumericalStateCrossedThresholdTriggerWithUnitBase",
    "EntityNumericalStateTriggerBase",
    "EntityNumericalStateTriggerWithUnitBase",
    "EntityOriginStateTriggerBase",
    "EntityTargetStateTriggerBase",
    "EntityTransitionTriggerBase",
    "EntityTriggerBase",
    "NotTriggeredInfo",
    "NotTriggeredReasonReporter",
    "PluggableAction",
    "PluggableActionsEntry",
    "StatelessEntityTriggerBase",
    "Trigger",
    "TriggerAction",
    "TriggerActionPayloadBuilder",
    "TriggerActionRunner",
    "TriggerActionType",
    "TriggerConfig",
    "TriggerData",
    "TriggerInfo",
    "TriggerNotTriggeredAction",
    "TriggerNotTriggeredReporter",
    "TriggerProtocol",
    "async_extract_devices",
    "async_extract_entities",
    "async_extract_targets",
    "async_get_all_descriptions",
    "async_initialize_triggers",
    "async_setup",
    "async_subscribe_platform_events",
    "async_validate_trigger_config",
    "make_entity_numerical_state_changed_trigger",
    "make_entity_numerical_state_changed_with_unit_trigger",
    "make_entity_numerical_state_crossed_threshold_trigger",
    "make_entity_numerical_state_crossed_threshold_with_unit_trigger",
    "make_entity_origin_state_trigger",
    "make_entity_target_state_trigger",
    "make_entity_transition_trigger",
    "make_numerical_state_changed_with_unit_schema",
    "starts_with_dot",
]

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

TRIGGER_PLATFORM_SUBSCRIPTIONS: HassKey[
    list[Callable[[set[str]], Coroutine[Any, Any, None]]]
] = HassKey("trigger_platform_subscriptions")


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
    """Register a trigger platform and notify listeners.

    If the trigger platform does not provide any triggers,
    listeners will not be notified.
    """
    new_triggers: set[str] = set()
    triggers = hass.data[TRIGGERS]

    if hasattr(platform, "async_get_triggers"):
        all_triggers = await platform.async_get_triggers(hass)
        for trigger_key in all_triggers:
            trigger_key = get_absolute_description_key(integration_domain, trigger_key)
            if trigger_key not in triggers:
                triggers[trigger_key] = integration_domain
                new_triggers.add(trigger_key)
        if not new_triggers:
            if not all_triggers:
                _LOGGER.debug(
                    "Integration %s returned no triggers in async_get_triggers",
                    integration_domain,
                )
            return
    elif hasattr(platform, "async_validate_trigger_config") or hasattr(
        platform, "TRIGGER_SCHEMA"
    ):
        if integration_domain in triggers:
            return
        triggers[integration_domain] = integration_domain
        new_triggers.add(integration_domain)
    else:
        _LOGGER.debug(
            "Integration %s does not provide trigger support, skipping",
            integration_domain,
        )
        return

    # We don't use gather here because gather adds additional overhead
    # when wrapping each coroutine in a task, and we expect our listeners
    # to call trigger.async_get_all_descriptions which will only yield
    # the first time it's called, after that it returns cached data.
    for listener in hass.data[TRIGGER_PLATFORM_SUBSCRIPTIONS]:
        try:
            await listener(new_triggers)
        except Exception:
            _LOGGER.exception("Error while notifying trigger platform listener")


class TriggerProtocol(Protocol):
    """Define the format of trigger modules.

    New implementations should only implement async_get_triggers.
    """

    async def async_get_triggers(self, hass: HomeAssistant) -> dict[str, type[Trigger]]:
        """Return the triggers provided by this integration."""

    TRIGGER_SCHEMA: probatio.Schema

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


class TriggerNotTriggeredAction(Protocol):
    """Protocol type for the did_not_trigger consumer callback.

    Sibling of the action callback. Invoked - instead of the action - when a
    trigger evaluated a relevant change but reported it did not fire.
    """

    @callback
    def __call__(
        self,
        run_variables: dict[str, Any],
        info: NotTriggeredInfo,
        context: Context | None = None,
    ) -> None:
        """Define did_not_trigger consumer callback type."""


class TriggerActionType(Protocol):
    """Protocol type for trigger action callback.

    Contrary to TriggerAction, this type supports both sync and async callables.
    """

    def __call__(
        self,
        run_variables: dict[str, Any],
        context: Context | None = None,
    ) -> Coroutine[Any, Any, Any] | Any:
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
    variables: TemplateVarsType
    trigger_data: TriggerData


@dataclass(slots=True)
class PluggableActionsEntry:
    """Holder to keep track of all plugs and actions for a given trigger."""

    plugs: set[PluggableAction] = field(default_factory=set)
    actions: dict[
        object,
        tuple[
            HassJob[[dict[str, Any], Context | None], Coroutine[Any, Any, None] | Any],
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
    hass: HomeAssistant, trigger_key: str
) -> tuple[str, TriggerProtocol]:
    platform_and_sub_type = trigger_key.split(".")
    platform = platform_and_sub_type[0]
    # Only apply aliases for old-style triggers (no sub_type).
    # New-style triggers (e.g. "event.received") use the integration domain directly.
    if len(platform_and_sub_type) == 1:
        platform = _PLATFORM_ALIASES.get(platform, platform)

    try:
        integration = await async_get_integration(hass, platform)
    except IntegrationNotFound:
        raise probatio.Invalid(f"Invalid trigger '{trigger_key}' specified") from None
    try:
        platform_module = await integration.async_get_platform("trigger")
    except ImportError:
        raise probatio.Invalid(
            f"Integration '{platform}' does not provide trigger support"
        ) from None

    # Ensure triggers are registered so descriptions can be loaded
    await _register_trigger_platform(hass, platform, platform_module)

    return platform, platform_module


async def async_validate_trigger_config(
    hass: HomeAssistant, trigger_config: list[ConfigType]
) -> list[ConfigType]:
    """Validate triggers."""
    config = []
    for conf in trigger_config:
        trigger_key: str = conf[CONF_PLATFORM]
        platform_domain, platform = await _async_get_trigger_platform(hass, trigger_key)
        if hasattr(platform, "async_get_triggers"):
            trigger_descriptors = await platform.async_get_triggers(hass)
            relative_trigger_key = get_relative_description_key(
                platform_domain, trigger_key
            )
            if not (trigger := trigger_descriptors.get(relative_trigger_key)):
                raise probatio.Invalid(f"Invalid trigger '{trigger_key}' specified")
            conf = await trigger.async_validate_complete_config(hass, conf)
        elif hasattr(platform, "async_validate_trigger_config"):
            conf = move_options_fields_to_top_level(conf, cv.TRIGGER_BASE_SCHEMA)
            conf = await platform.async_validate_trigger_config(hass, conf)
        else:
            conf = move_options_fields_to_top_level(conf, cv.TRIGGER_BASE_SCHEMA)
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
    if inspect.iscoroutinefunction(check_func):
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
        def with_vars(
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


async def _async_attach_trigger_cls(
    hass: HomeAssistant,
    trigger_cls: type[Trigger],
    trigger_key: str,
    conf: ConfigType,
    action: Callable,
    trigger_info: TriggerInfo,
    did_not_trigger: TriggerNotTriggeredAction | None = None,
) -> CALLBACK_TYPE:
    """Initialize a new Trigger class and attach it."""

    def action_payload_builder(
        extra_trigger_payload: dict[str, Any], description: str
    ) -> dict[str, Any]:
        """Build action variables."""
        payload = {
            "trigger": {
                **trigger_info["trigger_data"],
                CONF_PLATFORM: trigger_key,
                "description": description,
                **extra_trigger_payload,
            }
        }
        if CONF_VARIABLES in conf:
            trigger_variables = conf[CONF_VARIABLES]
            payload.update(trigger_variables.async_render(hass, payload))
        return payload

    report_not_triggered: TriggerNotTriggeredReporter | None = None
    if did_not_trigger is not None:
        not_triggered_action = did_not_trigger

        @callback
        def report_not_triggered(
            info: NotTriggeredInfo, context: Context | None = None
        ) -> None:
            """Forward a did-not-fire report to the consumer."""
            run_variables = {
                "trigger": {
                    **trigger_info["trigger_data"],
                    CONF_PLATFORM: trigger_key,
                }
            }
            # The consumer records a trace using the trace context variables.
            # Run it in a copied context so it does not disturb the trace of the
            # run that produced this state change (e.g. a chained automation).
            copy_context().run(not_triggered_action, run_variables, info, context)

    # Wrap sync action so that it is always async.
    # This simplifies the Trigger action runner interface by
    # always returning a coroutine, removing the need for
    # integrations to check for the return type when awaiting
    # the action.
    match get_hassjob_callable_job_type(action):
        case HassJobType.Executor:
            original_action = action

            async def wrapped_executor_action(
                run_variables: dict[str, Any], context: Context | None = None
            ) -> Any:
                """Wrap sync action to be called in executor."""
                return await hass.async_add_executor_job(
                    original_action, run_variables, context
                )

            action = wrapped_executor_action

        case HassJobType.Callback:
            original_action = action

            async def wrapped_callback_action(
                run_variables: dict[str, Any], context: Context | None = None
            ) -> Any:
                """Wrap callback action to be awaitable."""
                return original_action(run_variables, context)

            action = wrapped_callback_action

    trigger = trigger_cls(
        hass,
        TriggerConfig(
            key=trigger_key,
            target=conf.get(CONF_TARGET),
            options=conf.get(CONF_OPTIONS),
        ),
    )
    return await trigger.async_attach_action(
        action, action_payload_builder, did_not_trigger=report_not_triggered
    )


async def async_initialize_triggers(
    hass: HomeAssistant,
    trigger_config: list[ConfigType],
    action: Callable,
    domain: str,
    name: str,
    log_cb: Callable,
    home_assistant_start: bool | UndefinedType = UNDEFINED,
    variables: TemplateVarsType = None,
    *,
    did_not_trigger: TriggerNotTriggeredAction | None = None,
) -> CALLBACK_TYPE | None:
    """Initialize triggers.

    The optional ``did_not_trigger`` consumer is the sibling of ``action``,
    invoked - for new-style triggers that support it - when a trigger evaluates
    a relevant change but reports it did not fire. Old-style triggers ignore it.
    """
    if home_assistant_start is not UNDEFINED:
        report_usage(
            "passes `home_assistant_start` to `async_initialize_triggers`, which is "
            "deprecated and will be removed in Home Assistant 2027.8; the parameter "
            "no longer has any effect",
            breaks_in_ha_version="2027.8.0",
        )

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

        trigger_key: str = conf[CONF_PLATFORM]
        platform_domain, platform = await _async_get_trigger_platform(hass, trigger_key)
        trigger_id = conf.get(CONF_ID, f"{idx}")
        trigger_idx = f"{idx}"
        trigger_alias = conf.get(CONF_ALIAS)
        trigger_data = TriggerData(id=trigger_id, idx=trigger_idx, alias=trigger_alias)
        info = TriggerInfo(
            domain=domain,
            name=name,
            variables=variables,
            trigger_data=trigger_data,
        )

        if hasattr(platform, "async_get_triggers"):
            trigger_descriptors = await platform.async_get_triggers(hass)
            relative_trigger_key = get_relative_description_key(
                platform_domain, trigger_key
            )
            trigger_cls = trigger_descriptors[relative_trigger_key]
            coro = _async_attach_trigger_cls(
                hass, trigger_cls, trigger_key, conf, action, info, did_not_trigger
            )
        else:
            action_wrapper = _trigger_action_wrapper(hass, action, conf)
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


@callback
def async_extract_devices(trigger_conf: dict) -> list[str]:
    """Extract devices from a trigger config."""
    if trigger_conf[CONF_PLATFORM] == "device":
        return [trigger_conf[CONF_DEVICE_ID]]

    if (
        trigger_conf[CONF_PLATFORM] == "event"
        and CONF_EVENT_DATA in trigger_conf
        and CONF_DEVICE_ID in trigger_conf[CONF_EVENT_DATA]
        and isinstance(trigger_conf[CONF_EVENT_DATA][CONF_DEVICE_ID], str)
    ):
        return [trigger_conf[CONF_EVENT_DATA][CONF_DEVICE_ID]]

    if trigger_conf[CONF_PLATFORM] == "tag" and CONF_DEVICE_ID in trigger_conf:
        return trigger_conf[CONF_DEVICE_ID]  # type: ignore[no-any-return]

    if target_devices := async_extract_targets(trigger_conf, CONF_DEVICE_ID):
        return target_devices

    return []


@callback
def async_extract_entities(trigger_conf: dict) -> list[str]:
    """Extract entities from a trigger config."""
    if trigger_conf[CONF_PLATFORM] in ("state", "numeric_state"):
        return trigger_conf[CONF_ENTITY_ID]  # type: ignore[no-any-return]

    if trigger_conf[CONF_PLATFORM] == "time":
        # Each at time can be a time, an entity id, an entity id with
        # an offset, or a template.
        entity_ids: list[str] = []
        for at_time in trigger_conf[CONF_AT]:
            if isinstance(at_time, str) and valid_entity_id(at_time):
                entity_ids.append(at_time)
            elif isinstance(at_time, dict) and CONF_ENTITY_ID in at_time:
                entity_ids.append(at_time[CONF_ENTITY_ID])
        return entity_ids

    if trigger_conf[CONF_PLATFORM] == "device":
        # Only extract the entity if it has been resolved to an entity id
        # during validation; unvalidated configs hold an entity registry id.
        if isinstance(
            entity_id := trigger_conf.get(CONF_ENTITY_ID), str
        ) and valid_entity_id(entity_id):
            return [entity_id]
        return []

    if trigger_conf[CONF_PLATFORM] == "calendar":
        return [trigger_conf[CONF_OPTIONS][CONF_ENTITY_ID]]

    if trigger_conf[CONF_PLATFORM] == "zone":
        options = trigger_conf[CONF_OPTIONS]
        return [*options[CONF_ENTITY_ID], options[CONF_ZONE]]

    if trigger_conf[CONF_PLATFORM] in ("zone.entered", "zone.left"):
        return [
            *async_extract_targets(trigger_conf, CONF_ENTITY_ID),
            trigger_conf[CONF_OPTIONS][CONF_ZONE],
        ]

    if trigger_conf[CONF_PLATFORM] == "geo_location":
        return [trigger_conf[CONF_ZONE]]

    if trigger_conf[CONF_PLATFORM] == "sun":
        return ["sun.sun"]

    if (
        trigger_conf[CONF_PLATFORM] == "event"
        and CONF_EVENT_DATA in trigger_conf
        and CONF_ENTITY_ID in trigger_conf[CONF_EVENT_DATA]
        and isinstance(trigger_conf[CONF_EVENT_DATA][CONF_ENTITY_ID], str)
        and valid_entity_id(trigger_conf[CONF_EVENT_DATA][CONF_ENTITY_ID])
    ):
        return [trigger_conf[CONF_EVENT_DATA][CONF_ENTITY_ID]]

    if target_entities := async_extract_targets(trigger_conf, CONF_ENTITY_ID):
        return target_entities

    return []


@callback
def async_extract_targets(
    config: dict,
    target: Literal["entity_id", "device_id", "area_id", "floor_id", "label_id"],
) -> list[str]:
    """Extract targets from a target config."""
    if not (target_conf := config.get(CONF_TARGET)):
        return []
    if not (targets := target_conf.get(target)):
        return []
    return [targets] if isinstance(targets, str) else targets
