"""Common trigger classes and constants."""

import abc
import asyncio
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

import probatio

from homeassistant.const import CONF_OPTIONS, CONF_TARGET
from homeassistant.core import CALLBACK_TYPE, Context, HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.hass_dict import HassKey

TRIGGERS: HassKey[dict[str, str]] = HassKey("triggers")

_TRIGGER_SCHEMA = cv.TRIGGER_BASE_SCHEMA.extend(
    {
        probatio.Optional(CONF_OPTIONS): object,
        probatio.Optional(CONF_TARGET): cv.TARGET_FIELDS,
    }
)


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


@dataclass(slots=True, frozen=True)
class NotTriggeredInfo:
    """Diagnostics describing why a trigger evaluated a change but did not fire.

    Passed by a trigger to its ``did_not_trigger`` reporter, the sibling of the
    action runner that is called - in certain interesting cases - when the
    trigger does not fire. ``reason`` is a stable, machine-readable code; the
    optional ``data`` carries the evaluated context for the trace.
    """

    reason: str
    data: Mapping[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dict for storing in a trace."""
        result: dict[str, Any] = {"reason": self.reason}
        if self.data is not None:
            result["data"] = dict(self.data)
        return result


class TriggerNotTriggeredReporter(Protocol):
    """Protocol type for the did_not_trigger reporter passed to a trigger runner.

    A trigger calls this to report that it evaluated a relevant change but
    decided not to fire, supplying diagnostics for tracing.
    """

    @callback
    def __call__(
        self,
        info: NotTriggeredInfo,
        context: Context | None = None,
    ) -> None:
        """Report that the trigger did not fire."""


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
        *,
        did_not_trigger: TriggerNotTriggeredReporter | None = None,
    ) -> CALLBACK_TYPE:
        """Attach the trigger to an action.

        The optional ``did_not_trigger`` reporter is the sibling of the action
        runner: triggers may call it - in certain interesting cases - when they
        evaluate a relevant change but decide not to fire.
        """

        @callback
        def run_action(
            extra_trigger_payload: dict[str, Any],
            description: str,
            context: Context | None = None,
        ) -> asyncio.Task[Any]:
            """Run action with trigger variables."""

            payload = action_payload_builder(extra_trigger_payload, description)
            return self._hass.async_create_task(action(payload, context))

        return await self.async_attach_runner(run_action, did_not_trigger)

    @abc.abstractmethod
    async def async_attach_runner(
        self,
        run_action: TriggerActionRunner,
        did_not_trigger: TriggerNotTriggeredReporter | None = None,
    ) -> CALLBACK_TYPE:
        """Attach the trigger to an action runner."""
