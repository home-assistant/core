"""Classes to help gather user submissions."""
from __future__ import annotations

import abc
import asyncio
from collections.abc import Callable, Iterable, Mapping
from contextlib import suppress
import copy
from dataclasses import dataclass
from enum import StrEnum
from functools import partial
import logging
from types import MappingProxyType
from typing import Any, Required, TypedDict

import voluptuous as vol

from .core import HomeAssistant, callback
from .exceptions import HomeAssistantError
from .helpers.deprecation import (
    DeprecatedConstantEnum,
    all_with_deprecated_constants,
    check_if_deprecated_constant,
    dir_with_deprecated_constants,
)
from .helpers.frame import report
from .loader import async_suggest_report_issue
from .util import uuid as uuid_util

_LOGGER = logging.getLogger(__name__)


class FlowResultType(StrEnum):
    """Result type for a data entry flow."""

    FORM = "form"
    CREATE_ENTRY = "create_entry"
    ABORT = "abort"
    EXTERNAL_STEP = "external"
    EXTERNAL_STEP_DONE = "external_done"
    SHOW_PROGRESS = "progress"
    SHOW_PROGRESS_DONE = "progress_done"
    MENU = "menu"


# RESULT_TYPE_* is deprecated, to be removed in 2022.9
_DEPRECATED_RESULT_TYPE_FORM = DeprecatedConstantEnum(FlowResultType.FORM, "2025.1")
_DEPRECATED_RESULT_TYPE_CREATE_ENTRY = DeprecatedConstantEnum(
    FlowResultType.CREATE_ENTRY, "2025.1"
)
_DEPRECATED_RESULT_TYPE_ABORT = DeprecatedConstantEnum(FlowResultType.ABORT, "2025.1")
_DEPRECATED_RESULT_TYPE_EXTERNAL_STEP = DeprecatedConstantEnum(
    FlowResultType.EXTERNAL_STEP, "2025.1"
)
_DEPRECATED_RESULT_TYPE_EXTERNAL_STEP_DONE = DeprecatedConstantEnum(
    FlowResultType.EXTERNAL_STEP_DONE, "2025.1"
)
_DEPRECATED_RESULT_TYPE_SHOW_PROGRESS = DeprecatedConstantEnum(
    FlowResultType.SHOW_PROGRESS, "2025.1"
)
_DEPRECATED_RESULT_TYPE_SHOW_PROGRESS_DONE = DeprecatedConstantEnum(
    FlowResultType.SHOW_PROGRESS_DONE, "2025.1"
)
_DEPRECATED_RESULT_TYPE_MENU = DeprecatedConstantEnum(FlowResultType.MENU, "2025.1")

# Event that is fired when a flow is progressed via external or progress source.
EVENT_DATA_ENTRY_FLOW_PROGRESSED = "data_entry_flow_progressed"

FLOW_NOT_COMPLETE_STEPS = {
    FlowResultType.FORM,
    FlowResultType.EXTERNAL_STEP,
    FlowResultType.EXTERNAL_STEP_DONE,
    FlowResultType.SHOW_PROGRESS,
    FlowResultType.SHOW_PROGRESS_DONE,
    FlowResultType.MENU,
}

STEP_ID_OPTIONAL_STEPS = {
    FlowResultType.EXTERNAL_STEP,
    FlowResultType.FORM,
    FlowResultType.MENU,
    FlowResultType.SHOW_PROGRESS,
}


@dataclass(slots=True)
class BaseServiceInfo:
    """Base class for discovery ServiceInfo."""


class FlowError(HomeAssistantError):
    """Base class for data entry errors."""


class UnknownHandler(FlowError):
    """Unknown handler specified."""


class UnknownFlow(FlowError):
    """Unknown flow specified."""


class UnknownStep(FlowError):
    """Unknown step specified."""


# ignore misc is required as vol.Invalid is not typed
# mypy error: Class cannot subclass "Invalid" (has type "Any")
class InvalidData(vol.Invalid):  # type: ignore[misc]
    """Invalid data provided."""

    def __init__(
        self,
        message: str,
        path: list[str | vol.Marker] | None,
        error_message: str | None,
        schema_errors: dict[str, Any],
        **kwargs: Any,
    ) -> None:
        super().__init__(message, path, error_message, **kwargs)
        self.schema_errors = schema_errors


class AbortFlow(FlowError):
    """Exception to indicate a flow needs to be aborted."""

    def __init__(
        self, reason: str, description_placeholders: Mapping[str, str] | None = None
    ) -> None:
        """Initialize an abort flow exception."""
        super().__init__(f"Flow aborted: {reason}")
        self.reason = reason
        self.description_placeholders = description_placeholders


class FlowResult(TypedDict, total=False):
    """Typed result dict."""

    context: dict[str, Any]
    data_schema: vol.Schema | None
    data: Mapping[str, Any]
    description_placeholders: Mapping[str, str | None] | None
    description: str | None
    errors: dict[str, str] | None
    extra: str
    flow_id: Required[str]
    handler: Required[str]
    last_step: bool | None
    menu_options: list[str] | dict[str, str]
    minor_version: int
    options: Mapping[str, Any]
    preview: str | None
    progress_action: str
    progress_task: asyncio.Task[Any] | None
    reason: str
    required: bool
    result: Any
    step_id: str
    title: str
    type: FlowResultType
    url: str
    version: int


@callback
def _async_flow_handler_to_flow_result(
    flows: Iterable[FlowHandler], include_uninitialized: bool
) -> list[FlowResult]:
    """Convert a list of FlowHandler to a partial FlowResult that can be serialized."""
    results = []
    for flow in flows:
        if not include_uninitialized and flow.cur_step is None:
            continue
        result = FlowResult(
            flow_id=flow.flow_id,
            handler=flow.handler,
            context=flow.context,
        )
        if flow.cur_step:
            result["step_id"] = flow.cur_step["step_id"]
        results.append(result)
    return results


def _map_error_to_schema_errors(
    schema_errors: dict[str, Any],
    error: vol.Invalid,
    data_schema: vol.Schema,
) -> None:
    """Map an error to the correct position in the schema_errors.

    Raises ValueError if the error path could not be found in the schema.
    Limitation: Nested schemas are not supported and a ValueError will be raised.
    """
    schema = data_schema.schema
    error_path = error.path
    if not error_path or (path_part := error_path[0]) not in schema:
        raise ValueError("Could not find path in schema")

    if len(error_path) > 1:
        raise ValueError("Nested schemas are not supported")

    # path_part can also be vol.Marker, but we need a string key
    path_part_str = str(path_part)
    schema_errors[path_part_str] = error.error_message


class FlowManager(abc.ABC):
    """Manage all the flows that are in progress."""

    def __init__(
        self,
        hass: HomeAssistant,
    ) -> None:
        """Initialize the flow manager."""
        self.hass = hass
        self._preview: set[str] = set()
        self._progress: dict[str, FlowHandler] = {}
        self._handler_progress_index: dict[str, set[FlowHandler]] = {}
        self._init_data_process_index: dict[type, set[FlowHandler]] = {}

    @abc.abstractmethod
    async def async_create_flow(
        self,
        handler_key: str,
        *,
        context: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
    ) -> FlowHandler:
        """Create a flow for specified handler.

        Handler key is the domain of the component that we want to set up.
        """

    @abc.abstractmethod
    async def async_finish_flow(
        self, flow: FlowHandler, result: FlowResult
    ) -> FlowResult:
        """Finish a data entry flow."""

    async def async_post_init(self, flow: FlowHandler, result: FlowResult) -> None:
        """Entry has finished executing its first step asynchronously."""

    @callback
    def async_has_matching_flow(
        self, handler: str, match_context: dict[str, Any], data: Any
    ) -> bool:
        """Check if an existing matching flow is in progress.

        A flow with the same handler, context, and data.

        If match_context is passed, only return flows with a context that is a
        superset of match_context.
        """
        if not (flows := self._handler_progress_index.get(handler)):
            return False
        match_items = match_context.items()
        for progress in flows:
            if match_items <= progress.context.items() and progress.init_data == data:
                return True
        return False

    @callback
    def async_get(self, flow_id: str) -> FlowResult:
        """Return a flow in progress as a partial FlowResult."""
        if (flow := self._progress.get(flow_id)) is None:
            raise UnknownFlow
        return _async_flow_handler_to_flow_result([flow], False)[0]

    @callback
    def async_progress(self, include_uninitialized: bool = False) -> list[FlowResult]:
        """Return the flows in progress as a partial FlowResult."""
        return _async_flow_handler_to_flow_result(
            self._progress.values(), include_uninitialized
        )

    @callback
    def async_progress_by_handler(
        self,
        handler: str,
        include_uninitialized: bool = False,
        match_context: dict[str, Any] | None = None,
    ) -> list[FlowResult]:
        """Return the flows in progress by handler as a partial FlowResult.

        If match_context is specified, only return flows with a context that
        is a superset of match_context.
        """
        return _async_flow_handler_to_flow_result(
            self._async_progress_by_handler(handler, match_context),
            include_uninitialized,
        )

    @callback
    def async_progress_by_init_data_type(
        self,
        init_data_type: type,
        matcher: Callable[[Any], bool],
        include_uninitialized: bool = False,
    ) -> list[FlowResult]:
        """Return flows in progress init matching by data type as a partial FlowResult."""
        return _async_flow_handler_to_flow_result(
            (
                progress
                for progress in self._init_data_process_index.get(init_data_type, set())
                if matcher(progress.init_data)
            ),
            include_uninitialized,
        )

    @callback
    def _async_progress_by_handler(
        self, handler: str, match_context: dict[str, Any] | None
    ) -> list[FlowHandler]:
        """Return the flows in progress by handler.

        If match_context is specified, only return flows with a context that
        is a superset of match_context.
        """
        if not match_context:
            return list(self._handler_progress_index.get(handler, ()))
        match_context_items = match_context.items()
        return [
            progress
            for progress in self._handler_progress_index.get(handler, ())
            if match_context_items <= progress.context.items()
        ]

    async def async_init(
        self, handler: str, *, context: dict[str, Any] | None = None, data: Any = None
    ) -> FlowResult:
        """Start a data entry flow."""
        if context is None:
            context = {}
        flow = await self.async_create_flow(handler, context=context, data=data)
        if not flow:
            raise UnknownFlow("Flow was not created")
        flow.hass = self.hass
        flow.handler = handler
        flow.flow_id = uuid_util.random_uuid_hex()
        flow.context = context
        flow.init_data = data
        self._async_add_flow_progress(flow)

        result = await self._async_handle_step(flow, flow.init_step, data)

        if result["type"] != FlowResultType.ABORT:
            await self.async_post_init(flow, result)

        return result

    async def async_configure(
        self, flow_id: str, user_input: dict | None = None
    ) -> FlowResult:
        """Continue a data entry flow."""
        result: FlowResult | None = None
        while not result or result["type"] == FlowResultType.SHOW_PROGRESS_DONE:
            result = await self._async_configure(flow_id, user_input)
            flow = self._progress.get(flow_id)
            if flow and flow.deprecated_show_progress:
                break
        return result

    async def _async_configure(
        self, flow_id: str, user_input: dict | None = None
    ) -> FlowResult:
        """Continue a data entry flow."""
        if (flow := self._progress.get(flow_id)) is None:
            raise UnknownFlow

        cur_step = flow.cur_step
        assert cur_step is not None

        if (
            data_schema := cur_step.get("data_schema")
        ) is not None and user_input is not None:
            try:
                user_input = data_schema(user_input)
            except vol.Invalid as ex:
                raised_errors = [ex]
                if isinstance(ex, vol.MultipleInvalid):
                    raised_errors = ex.errors

                schema_errors: dict[str, Any] = {}
                for error in raised_errors:
                    try:
                        _map_error_to_schema_errors(schema_errors, error, data_schema)
                    except ValueError:
                        # If we get here, the path in the exception does not exist in the schema.
                        schema_errors.setdefault("base", []).append(str(error))
                raise InvalidData(
                    "Schema validation failed",
                    path=ex.path,
                    error_message=ex.error_message,
                    schema_errors=schema_errors,
                ) from ex

        # Handle a menu navigation choice
        if cur_step["type"] == FlowResultType.MENU and user_input:
            result = await self._async_handle_step(
                flow, user_input["next_step_id"], None
            )
        else:
            result = await self._async_handle_step(
                flow, cur_step["step_id"], user_input
            )

        if cur_step["type"] in (
            FlowResultType.EXTERNAL_STEP,
            FlowResultType.SHOW_PROGRESS,
        ):
            if cur_step["type"] == FlowResultType.EXTERNAL_STEP and result[
                "type"
            ] not in (
                FlowResultType.EXTERNAL_STEP,
                FlowResultType.EXTERNAL_STEP_DONE,
            ):
                raise ValueError(
                    "External step can only transition to "
                    "external step or external step done."
                )
            if cur_step["type"] == FlowResultType.SHOW_PROGRESS and result[
                "type"
            ] not in (
                FlowResultType.SHOW_PROGRESS,
                FlowResultType.SHOW_PROGRESS_DONE,
            ):
                raise ValueError(
                    "Show progress can only transition to show progress or show"
                    " progress done."
                )

            # If the result has changed from last result, fire event to update
            # the frontend. The result is considered to have changed if:
            # - The step has changed
            # - The step is same but result type is SHOW_PROGRESS and progress_action
            #   or description_placeholders has changed
            if cur_step["step_id"] != result.get("step_id") or (
                result["type"] == FlowResultType.SHOW_PROGRESS
                and (
                    cur_step["progress_action"] != result.get("progress_action")
                    or cur_step["description_placeholders"]
                    != result.get("description_placeholders")
                )
            ):
                # Tell frontend to reload the flow state.
                self.hass.bus.async_fire(
                    EVENT_DATA_ENTRY_FLOW_PROGRESSED,
                    {"handler": flow.handler, "flow_id": flow_id, "refresh": True},
                )

        return result

    @callback
    def async_abort(self, flow_id: str) -> None:
        """Abort a flow."""
        self._async_remove_flow_progress(flow_id)

    @callback
    def _async_add_flow_progress(self, flow: FlowHandler) -> None:
        """Add a flow to in progress."""
        if flow.init_data is not None:
            init_data_type = type(flow.init_data)
            self._init_data_process_index.setdefault(init_data_type, set()).add(flow)
        self._progress[flow.flow_id] = flow
        self._handler_progress_index.setdefault(flow.handler, set()).add(flow)

    @callback
    def _async_remove_flow_from_index(self, flow: FlowHandler) -> None:
        """Remove a flow from in progress."""
        if flow.init_data is not None:
            init_data_type = type(flow.init_data)
            self._init_data_process_index[init_data_type].remove(flow)
            if not self._init_data_process_index[init_data_type]:
                del self._init_data_process_index[init_data_type]
        handler = flow.handler
        self._handler_progress_index[handler].remove(flow)
        if not self._handler_progress_index[handler]:
            del self._handler_progress_index[handler]

    @callback
    def _async_remove_flow_progress(self, flow_id: str) -> None:
        """Remove a flow from in progress."""
        if (flow := self._progress.pop(flow_id, None)) is None:
            raise UnknownFlow
        self._async_remove_flow_from_index(flow)
        flow.async_cancel_progress_task()
        try:
            flow.async_remove()
        except Exception as err:  # pylint: disable=broad-except
            _LOGGER.exception("Error removing %s flow: %s", flow.handler, err)

    async def _async_handle_step(
        self, flow: FlowHandler, step_id: str, user_input: dict | BaseServiceInfo | None
    ) -> FlowResult:
        """Handle a step of a flow."""
        self._raise_if_step_does_not_exist(flow, step_id)

        method = f"async_step_{step_id}"
        try:
            result: FlowResult = await getattr(flow, method)(user_input)
        except AbortFlow as err:
            result = _create_abort_data(
                flow.flow_id, flow.handler, err.reason, err.description_placeholders
            )

        # Setup the flow handler's preview if needed
        if result.get("preview") is not None:
            await self._async_setup_preview(flow)

        if not isinstance(result["type"], FlowResultType):
            result["type"] = FlowResultType(result["type"])  # type: ignore[unreachable]
            report(
                (
                    "does not use FlowResultType enum for data entry flow result type. "
                    "This is deprecated and will stop working in Home Assistant 2022.9"
                ),
                error_if_core=False,
            )

        if (
            result["type"] == FlowResultType.SHOW_PROGRESS
            and (progress_task := result.pop("progress_task", None))
            and progress_task != flow.async_get_progress_task()
        ):
            # The flow's progress task was changed, register a callback on it
            async def call_configure() -> None:
                with suppress(UnknownFlow):
                    await self._async_configure(flow.flow_id)

            def schedule_configure(_: asyncio.Task) -> None:
                self.hass.async_create_task(call_configure())

            progress_task.add_done_callback(schedule_configure)
            flow.async_set_progress_task(progress_task)

        elif result["type"] != FlowResultType.SHOW_PROGRESS:
            flow.async_cancel_progress_task()

        if result["type"] in STEP_ID_OPTIONAL_STEPS:
            if "step_id" not in result:
                result["step_id"] = step_id

        if result["type"] in FLOW_NOT_COMPLETE_STEPS:
            self._raise_if_step_does_not_exist(flow, result["step_id"])
            flow.cur_step = result
            return result

        # We pass a copy of the result because we're mutating our version
        result = await self.async_finish_flow(flow, result.copy())

        # _async_finish_flow may change result type, check it again
        if result["type"] == FlowResultType.FORM:
            flow.cur_step = result
            return result

        # Abort and Success results both finish the flow
        self._async_remove_flow_progress(flow.flow_id)

        return result

    def _raise_if_step_does_not_exist(self, flow: FlowHandler, step_id: str) -> None:
        """Raise if the step does not exist."""
        method = f"async_step_{step_id}"

        if not hasattr(flow, method):
            self._async_remove_flow_progress(flow.flow_id)
            raise UnknownStep(
                f"Handler {self.__class__.__name__} doesn't support step {step_id}"
            )

    async def _async_setup_preview(self, flow: FlowHandler) -> None:
        """Set up preview for a flow handler."""
        if flow.handler not in self._preview:
            self._preview.add(flow.handler)
            await flow.async_setup_preview(self.hass)


class FlowHandler:
    """Handle a data entry flow."""

    # Set by flow manager
    cur_step: FlowResult | None = None

    # While not purely typed, it makes typehinting more useful for us
    # and removes the need for constant None checks or asserts.
    flow_id: str = None  # type: ignore[assignment]
    hass: HomeAssistant = None  # type: ignore[assignment]
    handler: str = None  # type: ignore[assignment]
    # Ensure the attribute has a subscriptable, but immutable, default value.
    context: dict[str, Any] = MappingProxyType({})  # type: ignore[assignment]

    # Set by _async_create_flow callback
    init_step = "init"

    # The initial data that was used to start the flow
    init_data: Any = None

    # Set by developer
    VERSION = 1
    MINOR_VERSION = 1

    __progress_task: asyncio.Task[Any] | None = None
    __no_progress_task_reported = False
    deprecated_show_progress = False

    @property
    def source(self) -> str | None:
        """Source that initialized the flow."""
        return self.context.get("source", None)  # type: ignore[no-any-return]

    @property
    def show_advanced_options(self) -> bool:
        """If we should show advanced options."""
        return self.context.get("show_advanced_options", False)  # type: ignore[no-any-return]

    def add_suggested_values_to_schema(
        self, data_schema: vol.Schema, suggested_values: Mapping[str, Any] | None
    ) -> vol.Schema:
        """Make a copy of the schema, populated with suggested values.

        For each schema marker matching items in `suggested_values`,
        the `suggested_value` will be set. The existing `suggested_value` will
        be left untouched if there is no matching item.
        """
        schema = {}
        for key, val in data_schema.schema.items():
            if isinstance(key, vol.Marker):
                # Exclude advanced field
                if (
                    key.description
                    and key.description.get("advanced")
                    and not self.show_advanced_options
                ):
                    continue

            new_key = key
            if (
                suggested_values
                and key in suggested_values
                and isinstance(key, vol.Marker)
            ):
                # Copy the marker to not modify the flow schema
                new_key = copy.copy(key)
                new_key.description = {"suggested_value": suggested_values[key]}
            schema[new_key] = val
        return vol.Schema(schema)

    @callback
    def async_show_form(
        self,
        *,
        step_id: str | None = None,
        data_schema: vol.Schema | None = None,
        errors: dict[str, str] | None = None,
        description_placeholders: Mapping[str, str | None] | None = None,
        last_step: bool | None = None,
        preview: str | None = None,
    ) -> FlowResult:
        """Return the definition of a form to gather user input.

        The step_id parameter is deprecated and will be removed in a future release.
        """
        flow_result = FlowResult(
            type=FlowResultType.FORM,
            flow_id=self.flow_id,
            handler=self.handler,
            data_schema=data_schema,
            errors=errors,
            description_placeholders=description_placeholders,
            last_step=last_step,  # Display next or submit button in frontend
            preview=preview,  # Display preview component in frontend
        )
        if step_id is not None:
            flow_result["step_id"] = step_id
        return flow_result

    @callback
    def async_create_entry(
        self,
        *,
        title: str | None = None,
        data: Mapping[str, Any],
        description: str | None = None,
        description_placeholders: Mapping[str, str] | None = None,
    ) -> FlowResult:
        """Finish flow."""
        flow_result = FlowResult(
            version=self.VERSION,
            minor_version=self.MINOR_VERSION,
            type=FlowResultType.CREATE_ENTRY,
            flow_id=self.flow_id,
            handler=self.handler,
            data=data,
            description=description,
            description_placeholders=description_placeholders,
            context=self.context,
        )
        if title is not None:
            flow_result["title"] = title
        return flow_result

    @callback
    def async_abort(
        self,
        *,
        reason: str,
        description_placeholders: Mapping[str, str] | None = None,
    ) -> FlowResult:
        """Abort the flow."""
        return _create_abort_data(
            self.flow_id, self.handler, reason, description_placeholders
        )

    @callback
    def async_external_step(
        self,
        *,
        step_id: str | None = None,
        url: str,
        description_placeholders: Mapping[str, str] | None = None,
    ) -> FlowResult:
        """Return the definition of an external step for the user to take.

        The step_id parameter is deprecated and will be removed in a future release.
        """
        flow_result = FlowResult(
            type=FlowResultType.EXTERNAL_STEP,
            flow_id=self.flow_id,
            handler=self.handler,
            url=url,
            description_placeholders=description_placeholders,
        )
        if step_id is not None:
            flow_result["step_id"] = step_id
        return flow_result

    @callback
    def async_external_step_done(self, *, next_step_id: str) -> FlowResult:
        """Return the definition of an external step for the user to take."""
        return FlowResult(
            type=FlowResultType.EXTERNAL_STEP_DONE,
            flow_id=self.flow_id,
            handler=self.handler,
            step_id=next_step_id,
        )

    @callback
    def async_show_progress(
        self,
        *,
        step_id: str | None = None,
        progress_action: str,
        description_placeholders: Mapping[str, str] | None = None,
        progress_task: asyncio.Task[Any] | None = None,
    ) -> FlowResult:
        """Show a progress message to the user, without user input allowed.

        The step_id parameter is deprecated and will be removed in a future release.
        """
        if progress_task is None and not self.__no_progress_task_reported:
            self.__no_progress_task_reported = True
            cls = self.__class__
            report_issue = async_suggest_report_issue(self.hass, module=cls.__module__)
            _LOGGER.warning(
                (
                    "%s::%s calls async_show_progress without passing a progress task, "
                    "this is not valid and will break in Home Assistant Core 2024.8. "
                    "Please %s"
                ),
                cls.__module__,
                cls.__name__,
                report_issue,
            )

        if progress_task is None:
            self.deprecated_show_progress = True

        flow_result = FlowResult(
            type=FlowResultType.SHOW_PROGRESS,
            flow_id=self.flow_id,
            handler=self.handler,
            progress_action=progress_action,
            description_placeholders=description_placeholders,
            progress_task=progress_task,
        )
        if step_id is not None:
            flow_result["step_id"] = step_id
        return flow_result

    @callback
    def async_show_progress_done(self, *, next_step_id: str) -> FlowResult:
        """Mark the progress done."""
        return FlowResult(
            type=FlowResultType.SHOW_PROGRESS_DONE,
            flow_id=self.flow_id,
            handler=self.handler,
            step_id=next_step_id,
        )

    @callback
    def async_show_menu(
        self,
        *,
        step_id: str | None = None,
        menu_options: list[str] | dict[str, str],
        description_placeholders: Mapping[str, str] | None = None,
    ) -> FlowResult:
        """Show a navigation menu to the user.

        Options dict maps step_id => i18n label
        The step_id parameter is deprecated and will be removed in a future release.
        """
        flow_result = FlowResult(
            type=FlowResultType.MENU,
            flow_id=self.flow_id,
            handler=self.handler,
            data_schema=vol.Schema({"next_step_id": vol.In(menu_options)}),
            menu_options=menu_options,
            description_placeholders=description_placeholders,
        )
        if step_id is not None:
            flow_result["step_id"] = step_id
        return flow_result

    @callback
    def async_remove(self) -> None:
        """Notification that the flow has been removed."""

    @staticmethod
    async def async_setup_preview(hass: HomeAssistant) -> None:
        """Set up preview."""

    @callback
    def async_cancel_progress_task(self) -> None:
        """Cancel in progress task."""
        if self.__progress_task and not self.__progress_task.done():
            self.__progress_task.cancel()
        self.__progress_task = None

    @callback
    def async_get_progress_task(self) -> asyncio.Task[Any] | None:
        """Get in progress task."""
        return self.__progress_task

    @callback
    def async_set_progress_task(
        self,
        progress_task: asyncio.Task[Any],
    ) -> None:
        """Set in progress task."""
        self.__progress_task = progress_task


@callback
def _create_abort_data(
    flow_id: str,
    handler: str,
    reason: str,
    description_placeholders: Mapping[str, str] | None = None,
) -> FlowResult:
    """Return the definition of an external step for the user to take."""
    return FlowResult(
        type=FlowResultType.ABORT,
        flow_id=flow_id,
        handler=handler,
        reason=reason,
        description_placeholders=description_placeholders,
    )


# These can be removed if no deprecated constant are in this module anymore
__getattr__ = partial(check_if_deprecated_constant, module_globals=globals())
__dir__ = partial(
    dir_with_deprecated_constants, module_globals_keys=[*globals().keys()]
)
__all__ = all_with_deprecated_constants(globals())
