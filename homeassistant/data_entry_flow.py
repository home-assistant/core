"""Classes to help gather user submissions."""
from __future__ import annotations

import abc
import asyncio
from collections.abc import Mapping
from types import MappingProxyType
from typing import Any, TypedDict
import uuid

import voluptuous as vol

from .core import HomeAssistant, callback
from .exceptions import HomeAssistantError

RESULT_TYPE_FORM = "form"
RESULT_TYPE_CREATE_ENTRY = "create_entry"
RESULT_TYPE_ABORT = "abort"
RESULT_TYPE_EXTERNAL_STEP = "external"
RESULT_TYPE_EXTERNAL_STEP_DONE = "external_done"
RESULT_TYPE_SHOW_PROGRESS = "progress"
RESULT_TYPE_SHOW_PROGRESS_DONE = "progress_done"

# Event that is fired when a flow is progressed via external or progress source.
EVENT_DATA_ENTRY_FLOW_PROGRESSED = "data_entry_flow_progressed"


class FlowError(HomeAssistantError):
    """Error while configuring an account."""


class UnknownHandler(FlowError):
    """Unknown handler specified."""


class UnknownFlow(FlowError):
    """Unknown flow specified."""


class UnknownStep(FlowError):
    """Unknown step specified."""


class AbortFlow(FlowError):
    """Exception to indicate a flow needs to be aborted."""

    def __init__(self, reason: str, description_placeholders: dict | None = None):
        """Initialize an abort flow exception."""
        super().__init__(f"Flow aborted: {reason}")
        self.reason = reason
        self.description_placeholders = description_placeholders


class FlowResult(TypedDict, total=False):
    """Typed result dict."""

    version: int
    type: str
    flow_id: str
    handler: str
    title: str
    data: Mapping[str, Any]
    step_id: str
    data_schema: vol.Schema
    extra: str
    required: bool
    errors: dict[str, str] | None
    description: str | None
    description_placeholders: dict[str, Any] | None
    progress_action: str
    url: str
    reason: str
    context: dict[str, Any]
    result: Any
    last_step: bool | None


class FlowManager(abc.ABC):
    """Manage all the flows that are in progress."""

    def __init__(
        self,
        hass: HomeAssistant,
    ) -> None:
        """Initialize the flow manager."""
        self.hass = hass
        self._initializing: dict[str, list[asyncio.Future]] = {}
        self._initialize_tasks: dict[str, list[asyncio.Task]] = {}
        self._progress: dict[str, Any] = {}

    async def async_wait_init_flow_finish(self, handler: str) -> None:
        """Wait till all flows in progress are initialized."""
        current = self._initializing.get(handler)

        if not current:
            return

        await asyncio.wait(current)

    @abc.abstractmethod
    async def async_create_flow(
        self,
        handler_key: Any,
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
        """Finish a config flow and add an entry."""

    async def async_post_init(self, flow: FlowHandler, result: FlowResult) -> None:
        """Entry has finished executing its first step asynchronously."""

    @callback
    def async_progress(self, include_uninitialized: bool = False) -> list[FlowResult]:
        """Return the flows in progress."""
        return [
            {
                "flow_id": flow.flow_id,
                "handler": flow.handler,
                "context": flow.context,
                "step_id": flow.cur_step["step_id"] if flow.cur_step else None,
            }
            for flow in self._progress.values()
            if include_uninitialized or flow.cur_step is not None
        ]

    async def async_init(
        self, handler: str, *, context: dict[str, Any] | None = None, data: Any = None
    ) -> FlowResult:
        """Start a configuration flow."""
        if context is None:
            context = {}

        init_done: asyncio.Future = asyncio.Future()
        self._initializing.setdefault(handler, []).append(init_done)

        task = asyncio.create_task(self._async_init(init_done, handler, context, data))
        self._initialize_tasks.setdefault(handler, []).append(task)

        try:
            flow, result = await task
        finally:
            self._initialize_tasks[handler].remove(task)
            self._initializing[handler].remove(init_done)

        if result["type"] != RESULT_TYPE_ABORT:
            await self.async_post_init(flow, result)

        return result

    async def _async_init(
        self,
        init_done: asyncio.Future,
        handler: str,
        context: dict,
        data: Any,
    ) -> tuple[FlowHandler, FlowResult]:
        """Run the init in a task to allow it to be canceled at shutdown."""
        flow = await self.async_create_flow(handler, context=context, data=data)
        if not flow:
            raise UnknownFlow("Flow was not created")
        flow.hass = self.hass
        flow.handler = handler
        flow.flow_id = uuid.uuid4().hex
        flow.context = context
        self._progress[flow.flow_id] = flow
        result = await self._async_handle_step(flow, flow.init_step, data, init_done)
        return flow, result

    async def async_shutdown(self) -> None:
        """Cancel any initializing flows."""
        for task_list in self._initialize_tasks.values():
            for task in task_list:
                task.cancel()

    async def async_configure(
        self, flow_id: str, user_input: dict | None = None
    ) -> FlowResult:
        """Continue a configuration flow."""
        flow = self._progress.get(flow_id)

        if flow is None:
            raise UnknownFlow

        cur_step = flow.cur_step

        if cur_step.get("data_schema") is not None and user_input is not None:
            user_input = cur_step["data_schema"](user_input)

        result = await self._async_handle_step(flow, cur_step["step_id"], user_input)

        if cur_step["type"] in (RESULT_TYPE_EXTERNAL_STEP, RESULT_TYPE_SHOW_PROGRESS):
            if cur_step["type"] == RESULT_TYPE_EXTERNAL_STEP and result["type"] not in (
                RESULT_TYPE_EXTERNAL_STEP,
                RESULT_TYPE_EXTERNAL_STEP_DONE,
            ):
                raise ValueError(
                    "External step can only transition to "
                    "external step or external step done."
                )
            if cur_step["type"] == RESULT_TYPE_SHOW_PROGRESS and result["type"] not in (
                RESULT_TYPE_SHOW_PROGRESS,
                RESULT_TYPE_SHOW_PROGRESS_DONE,
            ):
                raise ValueError(
                    "Show progress can only transition to show progress or show progress done."
                )

            # If the result has changed from last result, fire event to update
            # the frontend.
            if (
                cur_step["step_id"] != result.get("step_id")
                or result["type"] == RESULT_TYPE_SHOW_PROGRESS
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
        if self._progress.pop(flow_id, None) is None:
            raise UnknownFlow

    async def _async_handle_step(
        self,
        flow: Any,
        step_id: str,
        user_input: dict | None,
        step_done: asyncio.Future | None = None,
    ) -> FlowResult:
        """Handle a step of a flow."""
        method = f"async_step_{step_id}"

        if not hasattr(flow, method):
            self._progress.pop(flow.flow_id)
            if step_done:
                step_done.set_result(None)
            raise UnknownStep(
                f"Handler {flow.__class__.__name__} doesn't support step {step_id}"
            )

        try:
            result: FlowResult = await getattr(flow, method)(user_input)
        except AbortFlow as err:
            result = _create_abort_data(
                flow.flow_id, flow.handler, err.reason, err.description_placeholders
            )

        # Mark the step as done.
        # We do this before calling async_finish_flow because config entries will hit a
        # circular dependency where async_finish_flow sets up new entry, which needs the
        # integration to be set up, which is waiting for init to be done.
        if step_done:
            step_done.set_result(None)

        if result["type"] not in (
            RESULT_TYPE_FORM,
            RESULT_TYPE_EXTERNAL_STEP,
            RESULT_TYPE_CREATE_ENTRY,
            RESULT_TYPE_ABORT,
            RESULT_TYPE_EXTERNAL_STEP_DONE,
            RESULT_TYPE_SHOW_PROGRESS,
            RESULT_TYPE_SHOW_PROGRESS_DONE,
        ):
            raise ValueError(f"Handler returned incorrect type: {result['type']}")

        if result["type"] in (
            RESULT_TYPE_FORM,
            RESULT_TYPE_EXTERNAL_STEP,
            RESULT_TYPE_EXTERNAL_STEP_DONE,
            RESULT_TYPE_SHOW_PROGRESS,
            RESULT_TYPE_SHOW_PROGRESS_DONE,
        ):
            flow.cur_step = result
            return result

        # We pass a copy of the result because we're mutating our version
        result = await self.async_finish_flow(flow, result.copy())

        # _async_finish_flow may change result type, check it again
        if result["type"] == RESULT_TYPE_FORM:
            flow.cur_step = result
            return result

        # Abort and Success results both finish the flow
        self._progress.pop(flow.flow_id)

        return result


class FlowHandler:
    """Handle the configuration flow of a component."""

    # Set by flow manager
    cur_step: dict[str, str] | None = None

    # While not purely typed, it makes typehinting more useful for us
    # and removes the need for constant None checks or asserts.
    flow_id: str = None  # type: ignore
    hass: HomeAssistant = None  # type: ignore
    handler: str = None  # type: ignore
    # Ensure the attribute has a subscriptable, but immutable, default value.
    context: dict[str, Any] = MappingProxyType({})  # type: ignore

    # Set by _async_create_flow callback
    init_step = "init"

    # Set by developer
    VERSION = 1

    @property
    def source(self) -> str | None:
        """Source that initialized the flow."""
        if not hasattr(self, "context"):
            return None

        return self.context.get("source", None)

    @property
    def show_advanced_options(self) -> bool:
        """If we should show advanced options."""
        if not hasattr(self, "context"):
            return False

        return self.context.get("show_advanced_options", False)

    @callback
    def async_show_form(
        self,
        *,
        step_id: str,
        data_schema: vol.Schema = None,
        errors: dict[str, str] | None = None,
        description_placeholders: dict[str, Any] | None = None,
        last_step: bool | None = None,
    ) -> FlowResult:
        """Return the definition of a form to gather user input."""
        return {
            "type": RESULT_TYPE_FORM,
            "flow_id": self.flow_id,
            "handler": self.handler,
            "step_id": step_id,
            "data_schema": data_schema,
            "errors": errors,
            "description_placeholders": description_placeholders,
            "last_step": last_step,  # Display next or submit button in frontend
        }

    @callback
    def async_create_entry(
        self,
        *,
        title: str,
        data: Mapping[str, Any],
        description: str | None = None,
        description_placeholders: dict | None = None,
    ) -> FlowResult:
        """Finish config flow and create a config entry."""
        return {
            "version": self.VERSION,
            "type": RESULT_TYPE_CREATE_ENTRY,
            "flow_id": self.flow_id,
            "handler": self.handler,
            "title": title,
            "data": data,
            "description": description,
            "description_placeholders": description_placeholders,
        }

    @callback
    def async_abort(
        self, *, reason: str, description_placeholders: dict | None = None
    ) -> FlowResult:
        """Abort the config flow."""
        return _create_abort_data(
            self.flow_id, self.handler, reason, description_placeholders
        )

    @callback
    def async_external_step(
        self, *, step_id: str, url: str, description_placeholders: dict | None = None
    ) -> FlowResult:
        """Return the definition of an external step for the user to take."""
        return {
            "type": RESULT_TYPE_EXTERNAL_STEP,
            "flow_id": self.flow_id,
            "handler": self.handler,
            "step_id": step_id,
            "url": url,
            "description_placeholders": description_placeholders,
        }

    @callback
    def async_external_step_done(self, *, next_step_id: str) -> FlowResult:
        """Return the definition of an external step for the user to take."""
        return {
            "type": RESULT_TYPE_EXTERNAL_STEP_DONE,
            "flow_id": self.flow_id,
            "handler": self.handler,
            "step_id": next_step_id,
        }

    @callback
    def async_show_progress(
        self,
        *,
        step_id: str,
        progress_action: str,
        description_placeholders: dict | None = None,
    ) -> FlowResult:
        """Show a progress message to the user, without user input allowed."""
        return {
            "type": RESULT_TYPE_SHOW_PROGRESS,
            "flow_id": self.flow_id,
            "handler": self.handler,
            "step_id": step_id,
            "progress_action": progress_action,
            "description_placeholders": description_placeholders,
        }

    @callback
    def async_show_progress_done(self, *, next_step_id: str) -> FlowResult:
        """Mark the progress done."""
        return {
            "type": RESULT_TYPE_SHOW_PROGRESS_DONE,
            "flow_id": self.flow_id,
            "handler": self.handler,
            "step_id": next_step_id,
        }


@callback
def _create_abort_data(
    flow_id: str,
    handler: str,
    reason: str,
    description_placeholders: dict | None = None,
) -> FlowResult:
    """Return the definition of an external step for the user to take."""
    return {
        "type": RESULT_TYPE_ABORT,
        "flow_id": flow_id,
        "handler": handler,
        "reason": reason,
        "description_placeholders": description_placeholders,
    }
