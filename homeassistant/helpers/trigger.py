"""Triggers."""

from __future__ import annotations

import abc
import asyncio
from collections import defaultdict
from collections.abc import Callable, Coroutine, Iterable
from dataclasses import dataclass, field
from enum import StrEnum
import functools
import inspect
import logging
from typing import TYPE_CHECKING, Any, Final, Protocol, TypedDict, cast, override

import voluptuous as vol

from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_ABOVE,
    CONF_ALIAS,
    CONF_BELOW,
    CONF_ENABLED,
    CONF_ID,
    CONF_OPTIONS,
    CONF_PLATFORM,
    CONF_SELECTOR,
    CONF_TARGET,
    CONF_VARIABLES,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import (
    CALLBACK_TYPE,
    Context,
    HassJob,
    HassJobType,
    HomeAssistant,
    State,
    callback,
    get_hassjob_callable_job_type,
    is_callback,
    split_entity_id,
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

from . import config_validation as cv, selector
from .automation import (
    get_absolute_description_key,
    get_relative_description_key,
    move_options_fields_to_top_level,
)
from .integration_platform import async_process_integration_platforms
from .selector import TargetSelector
from .target import (
    TargetStateChangedData,
    async_track_target_selector_state_change_event,
)
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
TRIGGER_DISABLED_TRIGGERS: HassKey[set[str]] = HassKey("trigger_disabled_triggers")
TRIGGER_PLATFORM_SUBSCRIPTIONS: HassKey[
    list[Callable[[set[str]], Coroutine[Any, Any, None]]]
] = HassKey("trigger_platform_subscriptions")
TRIGGERS: HassKey[dict[str, str]] = HassKey("triggers")


# Basic schemas to sanity check the trigger descriptions,
# full validation is done by hassfest.triggers
_FIELD_DESCRIPTION_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_SELECTOR): selector.validate_selector,
    },
    extra=vol.ALLOW_EXTRA,
)

_TRIGGER_DESCRIPTION_SCHEMA = vol.Schema(
    {
        vol.Optional("target"): TargetSelector.CONFIG_SCHEMA,
        vol.Optional("fields"): vol.Schema({str: _FIELD_DESCRIPTION_SCHEMA}),
    },
    extra=vol.ALLOW_EXTRA,
)


def starts_with_dot(key: str) -> str:
    """Check if key starts with dot."""
    if not key.startswith("."):
        raise vol.Invalid("Key does not start with .")
    return key


_TRIGGERS_DESCRIPTION_SCHEMA = vol.Schema(
    {
        vol.Remove(vol.All(str, starts_with_dot)): object,
        cv.underscore_slug: vol.Any(None, _TRIGGER_DESCRIPTION_SCHEMA),
    }
)


async def async_setup(hass: HomeAssistant) -> None:
    """Set up the trigger helper."""
    from homeassistant.components import automation, labs  # noqa: PLC0415

    hass.data[TRIGGER_DESCRIPTION_CACHE] = {}
    hass.data[TRIGGER_DISABLED_TRIGGERS] = set()
    hass.data[TRIGGER_PLATFORM_SUBSCRIPTIONS] = []
    hass.data[TRIGGERS] = {}

    @callback
    def new_triggers_conditions_listener() -> None:
        """Handle new_triggers_conditions flag change."""
        # Invalidate the cache
        hass.data[TRIGGER_DESCRIPTION_CACHE] = {}
        hass.data[TRIGGER_DISABLED_TRIGGERS] = set()

    labs.async_listen(
        hass,
        automation.DOMAIN,
        automation.NEW_TRIGGERS_CONDITIONS_FEATURE_FLAG,
        new_triggers_conditions_listener,
    )

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

    If the trigger platform does not provide any triggers, or it is disabled,
    listeners will not be notified.
    """
    from homeassistant.components import automation  # noqa: PLC0415

    new_triggers: set[str] = set()

    if hasattr(platform, "async_get_triggers"):
        for trigger_key in await platform.async_get_triggers(hass):
            trigger_key = get_absolute_description_key(integration_domain, trigger_key)
            hass.data[TRIGGERS][trigger_key] = integration_domain
            new_triggers.add(trigger_key)
        if not new_triggers:
            _LOGGER.debug(
                "Integration %s returned no triggers in async_get_triggers",
                integration_domain,
            )
            return
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

    if automation.is_disabled_experimental_trigger(hass, integration_domain):
        _LOGGER.debug("Triggers for integration %s are disabled", integration_domain)
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


_TRIGGER_SCHEMA = cv.TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Optional(CONF_OPTIONS): object,
        vol.Optional(CONF_TARGET): cv.TARGET_FIELDS,
    }
)


class Trigger(abc.ABC):
    """Trigger class."""

    _hass: HomeAssistant

    @classmethod
    async def async_validate_complete_config(
        cls, hass: HomeAssistant, complete_config: ConfigType
    ) -> ConfigType:
        """Validate complete config.

        The complete config includes fields that are generic to all triggers,
        such as the alias or the ID.
        This method should be overridden by triggers that need to migrate
        from the old-style config.
        """
        complete_config = _TRIGGER_SCHEMA(complete_config)

        specific_config: ConfigType = {}
        for key in (CONF_OPTIONS, CONF_TARGET):
            if key in complete_config:
                specific_config[key] = complete_config.pop(key)
        specific_config = await cls.async_validate_config(hass, specific_config)

        for key in (CONF_OPTIONS, CONF_TARGET):
            if key in specific_config:
                complete_config[key] = specific_config[key]

        return complete_config

    @classmethod
    @abc.abstractmethod
    async def async_validate_config(
        cls, hass: HomeAssistant, config: ConfigType
    ) -> ConfigType:
        """Validate config."""

    def __init__(self, hass: HomeAssistant, config: TriggerConfig) -> None:
        """Initialize trigger."""
        self._hass = hass

    async def async_attach_action(
        self,
        action: TriggerAction,
        action_payload_builder: TriggerActionPayloadBuilder,
    ) -> CALLBACK_TYPE:
        """Attach the trigger to an action."""

        @callback
        def run_action(
            extra_trigger_payload: dict[str, Any],
            description: str,
            context: Context | None = None,
        ) -> asyncio.Task[Any]:
            """Run action with trigger variables."""

            payload = action_payload_builder(extra_trigger_payload, description)
            return self._hass.async_create_task(action(payload, context))

        return await self.async_attach_runner(run_action)

    @abc.abstractmethod
    async def async_attach_runner(
        self, run_action: TriggerActionRunner
    ) -> CALLBACK_TYPE:
        """Attach the trigger to an action runner."""


ATTR_BEHAVIOR: Final = "behavior"
BEHAVIOR_FIRST: Final = "first"
BEHAVIOR_LAST: Final = "last"
BEHAVIOR_ANY: Final = "any"

ENTITY_STATE_TRIGGER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_TARGET): cv.TARGET_FIELDS,
    }
)

ENTITY_STATE_TRIGGER_SCHEMA_FIRST_LAST = ENTITY_STATE_TRIGGER_SCHEMA.extend(
    {
        vol.Required(CONF_OPTIONS): {
            vol.Required(ATTR_BEHAVIOR, default=BEHAVIOR_ANY): vol.In(
                [BEHAVIOR_FIRST, BEHAVIOR_LAST, BEHAVIOR_ANY]
            ),
        },
        vol.Required(CONF_TARGET): cv.TARGET_FIELDS,
    }
)


class EntityTriggerBase(Trigger):
    """Trigger for entity state changes."""

    _domain: str
    _schema: vol.Schema = ENTITY_STATE_TRIGGER_SCHEMA_FIRST_LAST

    @override
    @classmethod
    async def async_validate_config(
        cls, hass: HomeAssistant, config: ConfigType
    ) -> ConfigType:
        """Validate config."""
        return cast(ConfigType, cls._schema(config))

    def __init__(self, hass: HomeAssistant, config: TriggerConfig) -> None:
        """Initialize the state trigger."""
        super().__init__(hass, config)
        if TYPE_CHECKING:
            assert config.target is not None
        self._options = config.options or {}
        self._target = config.target

    def is_valid_transition(self, from_state: State, to_state: State) -> bool:
        """Check if the origin state is valid and the state has changed."""
        if from_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return False

        return from_state.state != to_state.state

    @abc.abstractmethod
    def is_valid_state(self, state: State) -> bool:
        """Check if the new state matches the expected state(s)."""

    def check_all_match(self, entity_ids: set[str]) -> bool:
        """Check if all entity states match."""
        return all(
            self.is_valid_state(state)
            for entity_id in entity_ids
            if (state := self._hass.states.get(entity_id)) is not None
        )

    def check_one_match(self, entity_ids: set[str]) -> bool:
        """Check that only one entity state matches."""
        return (
            sum(
                self.is_valid_state(state)
                for entity_id in entity_ids
                if (state := self._hass.states.get(entity_id)) is not None
            )
            == 1
        )

    def entity_filter(self, entities: set[str]) -> set[str]:
        """Filter entities of this domain."""
        return {
            entity_id
            for entity_id in entities
            if split_entity_id(entity_id)[0] == self._domain
        }

    @override
    async def async_attach_runner(
        self, run_action: TriggerActionRunner
    ) -> CALLBACK_TYPE:
        """Attach the trigger to an action runner."""

        behavior = self._options.get(ATTR_BEHAVIOR)

        @callback
        def state_change_listener(
            target_state_change_data: TargetStateChangedData,
        ) -> None:
            """Listen for state changes and call action."""
            event = target_state_change_data.state_change_event
            entity_id = event.data["entity_id"]
            from_state = event.data["old_state"]
            to_state = event.data["new_state"]

            if not from_state or not to_state:
                return

            # The trigger should never fire if the new state is not valid
            if not self.is_valid_state(to_state):
                return

            # The trigger should never fire if the transition is not valid
            if not self.is_valid_transition(from_state, to_state):
                return

            if behavior == BEHAVIOR_LAST:
                if not self.check_all_match(
                    target_state_change_data.targeted_entity_ids
                ):
                    return
            elif behavior == BEHAVIOR_FIRST:
                if not self.check_one_match(
                    target_state_change_data.targeted_entity_ids
                ):
                    return

            run_action(
                {
                    ATTR_ENTITY_ID: entity_id,
                    "from_state": from_state,
                    "to_state": to_state,
                },
                f"state of {entity_id}",
                event.context,
            )

        return async_track_target_selector_state_change_event(
            self._hass, self._target, state_change_listener, self.entity_filter
        )


class EntityTargetStateTriggerBase(EntityTriggerBase):
    """Trigger for entity state changes to a specific state."""

    _to_states: set[str]

    def is_valid_transition(self, from_state: State, to_state: State) -> bool:
        """Check if the origin state is valid and the state has changed."""
        if from_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return False

        return (
            from_state.state != to_state.state
            and from_state.state not in self._to_states
        )

    def is_valid_state(self, state: State) -> bool:
        """Check if the new state matches the expected state."""
        return state.state in self._to_states


class EntityTransitionTriggerBase(EntityTriggerBase):
    """Trigger for entity state changes between specific states."""

    _from_states: set[str]
    _to_states: set[str]

    def is_valid_transition(self, from_state: State, to_state: State) -> bool:
        """Check if the origin state matches the expected ones."""
        if not super().is_valid_transition(from_state, to_state):
            return False

        return from_state.state in self._from_states

    def is_valid_state(self, state: State) -> bool:
        """Check if the new state matches the expected states."""
        return state.state in self._to_states


class EntityOriginStateTriggerBase(EntityTriggerBase):
    """Trigger for entity state changes from a specific state."""

    _from_state: str

    def is_valid_transition(self, from_state: State, to_state: State) -> bool:
        """Check if the origin state matches the expected one and that the state changed."""
        return (
            from_state.state == self._from_state and to_state.state != self._from_state
        )

    def is_valid_state(self, state: State) -> bool:
        """Check if the new state is not the same as the expected origin state."""
        return state.state != self._from_state


class EntityTargetStateAttributeTriggerBase(EntityTriggerBase):
    """Trigger for entity state attribute changes to a specific state."""

    _attribute: str
    _attribute_to_state: str

    def is_valid_transition(self, from_state: State, to_state: State) -> bool:
        """Check if the origin state is valid and the state has changed."""
        if from_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return False

        return from_state.attributes.get(self._attribute) != to_state.attributes.get(
            self._attribute
        )

    def is_valid_state(self, state: State) -> bool:
        """Check if the new state attribute matches the expected one."""
        return state.attributes.get(self._attribute) == self._attribute_to_state


def _validate_range[_T: dict[str, Any]](
    lower_limit: str, upper_limit: str
) -> Callable[[_T], _T]:
    """Generate range validator."""

    def _validate_range(value: _T) -> _T:
        above = value.get(lower_limit)
        below = value.get(upper_limit)

        if above is None or below is None:
            return value

        if isinstance(above, str) or isinstance(below, str):
            return value

        if above > below:
            raise vol.Invalid(
                (
                    f"A value can never be above {above} and below {below} at the same"
                    " time. You probably want two different triggers."
                ),
            )

        return value

    return _validate_range


_NUMBER_OR_ENTITY_CHOOSE_SCHEMA = vol.Schema(
    {
        vol.Required("chosen_selector"): vol.In(["number", "entity"]),
        vol.Optional("entity"): cv.entity_id,
        vol.Optional("number"): vol.Coerce(float),
    }
)


def _validate_number_or_entity(value: dict | float | str) -> float | str:
    """Validate number or entity selector result."""
    if isinstance(value, dict):
        _NUMBER_OR_ENTITY_CHOOSE_SCHEMA(value)
        return value[value["chosen_selector"]]  # type: ignore[no-any-return]
    return value


_number_or_entity = vol.All(
    _validate_number_or_entity, vol.Any(vol.Coerce(float), cv.entity_id)
)

NUMERICAL_ATTRIBUTE_CHANGED_TRIGGER_SCHEMA = ENTITY_STATE_TRIGGER_SCHEMA.extend(
    {
        vol.Required(CONF_OPTIONS): vol.All(
            {
                vol.Optional(CONF_ABOVE): _number_or_entity,
                vol.Optional(CONF_BELOW): _number_or_entity,
            },
            _validate_range(CONF_ABOVE, CONF_BELOW),
        )
    }
)


def _get_numerical_value(
    hass: HomeAssistant, entity_or_float: float | str
) -> float | None:
    """Get numerical value from float or entity state."""
    if isinstance(entity_or_float, str):
        if not (state := hass.states.get(entity_or_float)):
            # Entity not found
            return None
        try:
            return float(state.state)
        except (TypeError, ValueError):
            # Entity state is not a valid number
            return None
    return entity_or_float


class EntityNumericalStateAttributeChangedTriggerBase(EntityTriggerBase):
    """Trigger for numerical state attribute changes."""

    _attribute: str
    _schema = NUMERICAL_ATTRIBUTE_CHANGED_TRIGGER_SCHEMA

    _above: None | float | str
    _below: None | float | str

    def __init__(self, hass: HomeAssistant, config: TriggerConfig) -> None:
        """Initialize the state trigger."""
        super().__init__(hass, config)
        self._above = self._options.get(CONF_ABOVE)
        self._below = self._options.get(CONF_BELOW)

    def is_valid_transition(self, from_state: State, to_state: State) -> bool:
        """Check if the origin state is valid and the state has changed."""
        if from_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return False

        return from_state.attributes.get(self._attribute) != to_state.attributes.get(
            self._attribute
        )

    def is_valid_state(self, state: State) -> bool:
        """Check if the new state attribute matches the expected one."""
        # Handle missing or None attribute case first to avoid expensive exceptions
        if (_attribute_value := state.attributes.get(self._attribute)) is None:
            return False

        try:
            current_value = float(_attribute_value)
        except (TypeError, ValueError):
            # Attribute is not a valid number, don't trigger
            return False

        if self._above is not None:
            if (above := _get_numerical_value(self._hass, self._above)) is None:
                # Entity not found or invalid number, don't trigger
                return False
            if current_value <= above:
                # The number is not above the limit, don't trigger
                return False

        if self._below is not None:
            if (below := _get_numerical_value(self._hass, self._below)) is None:
                # Entity not found or invalid number, don't trigger
                return False
            if current_value >= below:
                # The number is not below the limit, don't trigger
                return False

        return True


CONF_LOWER_LIMIT = "lower_limit"
CONF_UPPER_LIMIT = "upper_limit"
CONF_THRESHOLD_TYPE = "threshold_type"


class ThresholdType(StrEnum):
    """Numerical threshold types."""

    ABOVE = "above"
    BELOW = "below"
    BETWEEN = "between"
    OUTSIDE = "outside"


def _validate_limits_for_threshold_type(value: dict[str, Any]) -> dict[str, Any]:
    """Validate that the correct limits are provided for the selected threshold type."""
    threshold_type = value.get(CONF_THRESHOLD_TYPE)

    if threshold_type == ThresholdType.ABOVE:
        if CONF_LOWER_LIMIT not in value:
            raise vol.Invalid("lower_limit is required for threshold_type 'above'")
    elif threshold_type == ThresholdType.BELOW:
        if CONF_UPPER_LIMIT not in value:
            raise vol.Invalid("upper_limit is required for threshold_type 'below'")
    elif threshold_type in (ThresholdType.BETWEEN, ThresholdType.OUTSIDE):
        if CONF_LOWER_LIMIT not in value or CONF_UPPER_LIMIT not in value:
            raise vol.Invalid(
                "Both lower_limit and upper_limit are required for"
                f" threshold_type '{threshold_type}'"
            )

    return value


NUMERICAL_ATTRIBUTE_CROSSED_THRESHOLD_SCHEMA = ENTITY_STATE_TRIGGER_SCHEMA.extend(
    {
        vol.Required(CONF_OPTIONS): vol.All(
            {
                vol.Required(ATTR_BEHAVIOR, default=BEHAVIOR_ANY): vol.In(
                    [BEHAVIOR_FIRST, BEHAVIOR_LAST, BEHAVIOR_ANY]
                ),
                vol.Optional(CONF_LOWER_LIMIT): _number_or_entity,
                vol.Optional(CONF_UPPER_LIMIT): _number_or_entity,
                vol.Required(CONF_THRESHOLD_TYPE): ThresholdType,
            },
            _validate_range(CONF_LOWER_LIMIT, CONF_UPPER_LIMIT),
            _validate_limits_for_threshold_type,
        )
    }
)


class EntityNumericalStateAttributeCrossedThresholdTriggerBase(EntityTriggerBase):
    """Trigger for numerical state attribute changes.

    This trigger only fires when the observed attribute changes from not within to within
    the defined threshold.
    """

    _attribute: str
    _schema = NUMERICAL_ATTRIBUTE_CROSSED_THRESHOLD_SCHEMA

    _lower_limit: float | str | None = None
    _upper_limit: float | str | None = None
    _threshold_type: ThresholdType

    def __init__(self, hass: HomeAssistant, config: TriggerConfig) -> None:
        """Initialize the state trigger."""
        super().__init__(hass, config)
        self._lower_limit = self._options.get(CONF_LOWER_LIMIT)
        self._upper_limit = self._options.get(CONF_UPPER_LIMIT)
        self._threshold_type = self._options[CONF_THRESHOLD_TYPE]

    def is_valid_transition(self, from_state: State, to_state: State) -> bool:
        """Check if the origin state is valid and the state has changed."""
        if from_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return False

        return not self.is_valid_state(from_state)

    def is_valid_state(self, state: State) -> bool:
        """Check if the new state attribute matches the expected one."""
        if self._lower_limit is not None:
            if (
                lower_limit := _get_numerical_value(self._hass, self._lower_limit)
            ) is None:
                # Entity not found or invalid number, don't trigger
                return False

        if self._upper_limit is not None:
            if (
                upper_limit := _get_numerical_value(self._hass, self._upper_limit)
            ) is None:
                # Entity not found or invalid number, don't trigger
                return False

        # Handle missing or None attribute case first to avoid expensive exceptions
        if (_attribute_value := state.attributes.get(self._attribute)) is None:
            return False

        try:
            current_value = float(_attribute_value)
        except (TypeError, ValueError):
            # Attribute is not a valid number, don't trigger
            return False

        # Note: We do not need to check for lower_limit/upper_limit being None here
        # because of the validation done in the schema.
        if self._threshold_type == ThresholdType.ABOVE:
            return current_value > lower_limit  # type: ignore[operator]
        if self._threshold_type == ThresholdType.BELOW:
            return current_value < upper_limit  # type: ignore[operator]

        # Mode is BETWEEN or OUTSIDE
        between = lower_limit < current_value < upper_limit  # type: ignore[operator]
        if self._threshold_type == ThresholdType.BETWEEN:
            return between
        return not between


def make_entity_target_state_trigger(
    domain: str, to_states: str | set[str]
) -> type[EntityTargetStateTriggerBase]:
    """Create a trigger for entity state changes to specific state(s)."""

    if isinstance(to_states, str):
        to_states_set = {to_states}
    else:
        to_states_set = to_states

    class CustomTrigger(EntityTargetStateTriggerBase):
        """Trigger for entity state changes."""

        _domain = domain
        _to_states = to_states_set

    return CustomTrigger


def make_entity_transition_trigger(
    domain: str, *, from_states: set[str], to_states: set[str]
) -> type[EntityTransitionTriggerBase]:
    """Create a trigger for entity state changes between specific states."""

    class CustomTrigger(EntityTransitionTriggerBase):
        """Trigger for conditional entity state changes."""

        _domain = domain
        _from_states = from_states
        _to_states = to_states

    return CustomTrigger


def make_entity_origin_state_trigger(
    domain: str, *, from_state: str
) -> type[EntityOriginStateTriggerBase]:
    """Create a trigger for entity state changes from a specific state."""

    class CustomTrigger(EntityOriginStateTriggerBase):
        """Trigger for entity "from state" changes."""

        _domain = domain
        _from_state = from_state

    return CustomTrigger


def make_entity_numerical_state_attribute_changed_trigger(
    domain: str, attribute: str
) -> type[EntityNumericalStateAttributeChangedTriggerBase]:
    """Create a trigger for numerical state attribute change."""

    class CustomTrigger(EntityNumericalStateAttributeChangedTriggerBase):
        """Trigger for numerical state attribute changes."""

        _domain = domain
        _attribute = attribute

    return CustomTrigger


def make_entity_numerical_state_attribute_crossed_threshold_trigger(
    domain: str, attribute: str
) -> type[EntityNumericalStateAttributeCrossedThresholdTriggerBase]:
    """Create a trigger for numerical state attribute change."""

    class CustomTrigger(EntityNumericalStateAttributeCrossedThresholdTriggerBase):
        """Trigger for numerical state attribute changes."""

        _domain = domain
        _attribute = attribute

    return CustomTrigger


def make_entity_target_state_attribute_trigger(
    domain: str, attribute: str, to_state: str
) -> type[EntityTargetStateAttributeTriggerBase]:
    """Create a trigger for entity state attribute changes to a specific state."""

    class CustomTrigger(EntityTargetStateAttributeTriggerBase):
        """Trigger for entity state changes."""

        _domain = domain
        _attribute = attribute
        _attribute_to_state = to_state

    return CustomTrigger


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


@dataclass(slots=True, frozen=True)
class TriggerConfig:
    """Trigger config."""

    key: str  # The key used to identify the trigger, e.g. "zwave.event"
    target: dict[str, Any] | None = None
    options: dict[str, Any] | None = None


class TriggerActionRunner(Protocol):
    """Protocol type for the trigger action runner helper callback."""

    @callback
    def __call__(
        self,
        extra_trigger_payload: dict[str, Any],
        description: str,
        context: Context | None = None,
    ) -> asyncio.Task[Any]:
        """Define trigger action runner type.

        Returns:
            A Task that allows awaiting for the action to finish.
        """


class TriggerActionPayloadBuilder(Protocol):
    """Protocol type for the trigger action payload builder."""

    def __call__(
        self, extra_trigger_payload: dict[str, Any], description: str
    ) -> dict[str, Any]:
        """Define trigger action payload builder type."""


class TriggerAction(Protocol):
    """Protocol type for trigger action callback."""

    async def __call__(
        self, run_variables: dict[str, Any], context: Context | None = None
    ) -> Any:
        """Define action callback type."""


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
    from homeassistant.components import automation  # noqa: PLC0415

    platform_and_sub_type = trigger_key.split(".")
    platform = platform_and_sub_type[0]
    platform = _PLATFORM_ALIASES.get(platform, platform)

    if automation.is_disabled_experimental_trigger(hass, platform):
        raise vol.Invalid(
            f"Trigger '{trigger_key}' requires the experimental 'New triggers and "
            "conditions' feature to be enabled in Home Assistant Labs settings "
            f"(feature flag: '{automation.NEW_TRIGGERS_CONDITIONS_FEATURE_FLAG}')"
        )

    try:
        integration = await async_get_integration(hass, platform)
    except IntegrationNotFound:
        raise vol.Invalid(f"Invalid trigger '{trigger_key}' specified") from None
    try:
        return platform, await integration.async_get_platform("trigger")
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
        trigger_key: str = conf[CONF_PLATFORM]
        platform_domain, platform = await _async_get_trigger_platform(hass, trigger_key)
        if hasattr(platform, "async_get_triggers"):
            trigger_descriptors = await platform.async_get_triggers(hass)
            relative_trigger_key = get_relative_description_key(
                platform_domain, trigger_key
            )
            if not (trigger := trigger_descriptors.get(relative_trigger_key)):
                raise vol.Invalid(f"Invalid trigger '{trigger_key}' specified")
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

    # Wrap sync action so that it is always async.
    # This simplifies the Trigger action runner interface by always returning a coroutine,
    # removing the need for integrations to check for the return type when awaiting the action.
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
    return await trigger.async_attach_action(action, action_payload_builder)


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

        trigger_key: str = conf[CONF_PLATFORM]
        platform_domain, platform = await _async_get_trigger_platform(hass, trigger_key)
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

        if hasattr(platform, "async_get_triggers"):
            trigger_descriptors = await platform.async_get_triggers(hass)
            relative_trigger_key = get_relative_description_key(
                platform_domain, trigger_key
            )
            trigger_cls = trigger_descriptors[relative_trigger_key]
            coro = _async_attach_trigger_cls(
                hass, trigger_cls, trigger_key, conf, action, info
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


def _load_triggers_file(integration: Integration) -> dict[str, Any]:
    """Load triggers file for an integration."""
    try:
        return cast(
            dict[str, Any],
            _TRIGGERS_DESCRIPTION_SCHEMA(
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
    integrations: Iterable[Integration],
) -> dict[str, dict[str, Any]]:
    """Load trigger files for multiple integrations."""
    return {
        integration.domain: {
            get_absolute_description_key(integration.domain, key): value
            for key, value in _load_triggers_file(integration).items()
        }
        for integration in integrations
    }


async def async_get_all_descriptions(
    hass: HomeAssistant,
) -> dict[str, dict[str, Any] | None]:
    """Return descriptions (i.e. user documentation) for all triggers."""
    from homeassistant.components import automation  # noqa: PLC0415

    descriptions_cache = hass.data[TRIGGER_DESCRIPTION_CACHE]

    triggers = hass.data[TRIGGERS]
    # See if there are new triggers not seen before.
    # Any trigger that we saw before already has an entry in description_cache.
    all_triggers = set(triggers)
    previous_all_triggers = set(descriptions_cache)
    # If the triggers are the same, we can return the cache

    # mypy complains: Invalid index type "HassKey[set[str]]" for "HassDict"
    if previous_all_triggers | hass.data[TRIGGER_DISABLED_TRIGGERS] == all_triggers:  # type: ignore[index]
        return descriptions_cache

    # Files we loaded for missing descriptions
    new_triggers_descriptions: dict[str, dict[str, Any]] = {}
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
                _load_triggers_files, integrations
            )

    # Make a copy of the old cache and add missing descriptions to it
    new_descriptions_cache = descriptions_cache.copy()
    for missing_trigger in missing_triggers:
        domain = triggers[missing_trigger]
        if automation.is_disabled_experimental_trigger(hass, domain):
            hass.data[TRIGGER_DISABLED_TRIGGERS].add(missing_trigger)
            continue

        if (
            yaml_description := new_triggers_descriptions.get(domain, {}).get(
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
        if (target := yaml_description.get("target")) is not None:
            description["target"] = target

        new_descriptions_cache[missing_trigger] = description
    hass.data[TRIGGER_DESCRIPTION_CACHE] = new_descriptions_cache
    return new_descriptions_cache
