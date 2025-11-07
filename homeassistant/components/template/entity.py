"""Template entity base class."""

from abc import abstractmethod
from collections.abc import Callable, Sequence
from enum import StrEnum
import logging
from typing import Any

import voluptuous as vol

from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_OPTIMISTIC,
    CONF_STATE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import Context, HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.entity import Entity, async_generate_entity_id
from homeassistant.helpers.script import Script, _VarsType
from homeassistant.helpers.template import Template, TemplateStateFromEntityId
from homeassistant.helpers.typing import ConfigType

from .const import CONF_DEFAULT_ENTITY_ID, RESULT_OFF, RESULT_ON

_LOGGER = logging.getLogger(__name__)


class AbstractTemplateEntity(Entity):
    """Actions linked to a template entity."""

    _entity_id_format: str
    _optimistic_entity: bool = False
    _extra_optimistic_options: tuple[str, ...] | None = None
    _template: Template | None = None

    def __init__(
        self,
        hass: HomeAssistant,
        config: ConfigType,
    ) -> None:
        """Initialize the entity."""

        self.hass = hass
        self._action_scripts: dict[str, Script] = {}
        self._result_handler = TemplateResultHandler(self)

        if self._optimistic_entity:
            optimistic = config.get(CONF_OPTIMISTIC)

            self._template = config.get(CONF_STATE)

            assumed_optimistic = self._template is None
            if self._extra_optimistic_options:
                assumed_optimistic = assumed_optimistic and all(
                    config.get(option) is None
                    for option in self._extra_optimistic_options
                )

            self._attr_assumed_state = optimistic or (
                optimistic is None and assumed_optimistic
            )

        if (default_entity_id := config.get(CONF_DEFAULT_ENTITY_ID)) is not None:
            _, _, object_id = default_entity_id.partition(".")
            self.entity_id = async_generate_entity_id(
                self._entity_id_format, object_id, hass=self.hass
            )

        device_registry = dr.async_get(hass)
        if (device_id := config.get(CONF_DEVICE_ID)) is not None:
            self.device_entry = device_registry.async_get(device_id)

    @property
    @abstractmethod
    def referenced_blueprint(self) -> str | None:
        """Return referenced blueprint or None."""

    @callback
    @abstractmethod
    def _render_script_variables(self) -> dict:
        """Render configured variables."""

    def add_script(
        self,
        script_id: str,
        config: Sequence[dict[str, Any]],
        name: str,
        domain: str,
    ):
        """Add an action script."""

        self._action_scripts[script_id] = Script(
            self.hass,
            config,
            f"{name} {script_id}",
            domain,
        )

    async def async_run_script(
        self,
        script: Script,
        *,
        run_variables: _VarsType | None = None,
        context: Context | None = None,
    ) -> None:
        """Run an action script."""
        if run_variables is None:
            run_variables = {}
        await script.async_run(
            run_variables={
                "this": TemplateStateFromEntityId(self.hass, self.entity_id),
                **self._render_script_variables(),
                **run_variables,
            },
            context=context,
        )


def log_result_error(
    entity: AbstractTemplateEntity,
    attribute: str,
    value: Any,
    expected: tuple[str, ...] | str,
) -> None:
    """Log a template result error."""

    # in some cases, like `preview` entities, the entity_id does not exist.
    if entity.entity_id is None:
        message = f"Received invalid {attribute}: {value} for entity {entity.name}, %s"
    else:
        message = (
            f"Received invalid {entity.entity_id.split('.')[0]} {attribute}"
            f": {value} for entity {entity.entity_id}, %s"
        )

    _LOGGER.error(
        message,
        expected if isinstance(expected, str) else "expected: " + ", ".join(expected),
    )


def _check_result_for_none(result: Any, none_on_unknown_unavailable: bool) -> bool:
    """Checks the result for none, unknown, unavailable."""
    if result is None:
        return True

    if none_on_unknown_unavailable and isinstance(result, str):
        return result.lower() in (STATE_UNAVAILABLE, STATE_UNKNOWN)

    return False


class TemplateResultHandler:
    """Class for converting template results."""

    def __init__(self, entity: AbstractTemplateEntity) -> None:
        """Initialize the converter."""
        self._entity = entity

    def enum[T: StrEnum](
        self,
        attribute: str,
        state_enum: type[T],
        state_on: T | None = None,
        state_off: T | None = None,
        none_on_unknown_unavailable: bool = False,
    ) -> Callable[[Any], T | None]:
        """Converts the template result to an StrEnum.

        All strings will attempt to convert to the StrEnum
        If state_on or state_off are provided, boolean values will return the
         enum that represents each boolean value.
        Anything that cannot convert will result in None.
        """

        def convert(result: Any) -> T | None:
            if _check_result_for_none(result, none_on_unknown_unavailable):
                return None

            if isinstance(result, str):
                value = result.lower().strip()
                try:
                    return state_enum(value)
                except ValueError:
                    pass

            if state_on or state_off:
                try:
                    bool_value = cv.boolean(result)
                    if state_on and bool_value:
                        return state_on

                    if state_off and not bool_value:
                        return state_off

                except vol.Invalid:
                    pass

            expected = tuple(s.value for s in state_enum)
            if state_on:
                expected += RESULT_ON
            if state_off:
                expected += RESULT_OFF

            log_result_error(
                self._entity,
                attribute,
                result,
                expected,
            )
            return None

        return convert

    def boolean(
        self,
        attribute: str,
        as_true: tuple[str, ...] | None = None,
        as_false: tuple[str, ...] | None = None,
        none_on_unknown_unavailable: bool = False,
    ) -> Callable[[Any], bool | None]:
        """Convert the result to a boolean.

        True/not 0/'1'/'true'/'yes'/'on'/'enable' are considered truthy
        False/0/'0'/'false'/'no'/'off'/'disable' are considered falsy
        Additional values provided by as_true are considered truthy
        Additional values provided by as_false are considered truthy
        All other values are None
        """

        def convert(result: Any) -> bool | None:
            if _check_result_for_none(result, none_on_unknown_unavailable):
                return None

            if isinstance(result, bool):
                return result

            if isinstance(result, str) and (as_true or as_false):
                value = result.lower().strip()
                if as_true and value in as_true:
                    return True
                if as_false and value in as_false:
                    return False

            try:
                return cv.boolean(result)
            except vol.Invalid:
                log_result_error(
                    self._entity,
                    attribute,
                    result,
                    RESULT_ON + RESULT_OFF,
                )
                return None

        return convert

    def number(
        self,
        attribute: str,
        minimum: float | None = None,
        maximum: float | None = None,
        return_type: type[float] | type[int] = float,
        none_on_unknown_unavailable: bool = False,
    ) -> Callable[[Any], float | int | None]:
        """Convert the result to a number (float or int).

        Any value in the range is converted to a float or int
        All other values are None
        """
        message = "expected a number"
        if minimum is not None and maximum is not None:
            message = f"{message} between {minimum:0.1f} and {maximum:0.1f}"
        elif minimum is not None and maximum is None:
            message = f"{message} greater than or equal to {minimum:0.1f}"
        elif minimum is None and maximum is not None:
            message = f"{message} less than or equal to {maximum:0.1f}"

        def convert(result: Any) -> float | int | None:
            if _check_result_for_none(result, none_on_unknown_unavailable):
                return None

            if (result_type := type(result)) is bool:
                log_result_error(self._entity, attribute, result, message)
                return None

            if isinstance(result, (float, int)):
                value = result
                if return_type is int and result_type is float:
                    value = int(value)
                elif return_type is float and result_type is int:
                    value = float(value)
            else:
                try:
                    value = vol.Coerce(float)(result)
                    if return_type is int:
                        value = int(value)
                except vol.Invalid:
                    log_result_error(self._entity, attribute, result, message)
                    return None

            if minimum is None and maximum is None:
                return value

            if (
                (
                    minimum is not None
                    and maximum is not None
                    and minimum <= value <= maximum
                )
                or (minimum is not None and maximum is None and value >= minimum)
                or (minimum is None and maximum is not None and value <= maximum)
            ):
                return value

            log_result_error(self._entity, attribute, result, message)
            return None

        return convert

    def list_of_strings(
        self,
        attribute: str,
        none_on_empty: bool = False,
        none_on_unknown_unavailable: bool = False,
    ) -> Callable[[Any], list[str] | None]:
        """Convert the result to a list of strings.

        This ensures the result is a list of strings.
        All other values that are not lists will result in None.

        none_on_empty will cause the converter to return None when the list is empty.
        """

        def convert(result: Any) -> list[str] | None:
            if _check_result_for_none(result, none_on_unknown_unavailable):
                return None

            if not isinstance(result, list):
                log_result_error(
                    self._entity,
                    attribute,
                    result,
                    "expected a list of strings",
                )
                return None

            if none_on_empty and len(result) == 0:
                return None

            # Ensure the result are strings.
            return [str(v) for v in result]

        return convert

    def item_in_list[T](
        self,
        attribute: str,
        items: list[Any] | None,
        items_attribute: str | None = None,
        none_on_unknown_unavailable: bool = False,
    ) -> Callable[[Any], Any | None]:
        """Convert the result to an item inside a list.

        Returns the result if the result is inside the list.
        All results that are not inside the list will return None.
        """

        def convert(result: Any) -> Any | None:
            if _check_result_for_none(result, none_on_unknown_unavailable):
                return None

            if items is None or (len(items) == 0):
                if items_attribute:
                    log_result_error(
                        self._entity,
                        attribute,
                        result,
                        f"{items_attribute} is empty",
                    )

                return None

            if result not in items:
                log_result_error(
                    self._entity,
                    attribute,
                    result,
                    tuple(str(v) for v in items),
                )
                return None

            return result

        return convert
