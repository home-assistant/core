"""Classes to help gather user submissions."""
import abc
import logging
from typing import Any, Dict, List, Optional, cast
import uuid

import voluptuous as vol

from .core import HomeAssistant, callback
from .exceptions import HomeAssistantError

_LOGGER = logging.getLogger(__name__)

RESULT_TYPE_FORM = "form"
RESULT_TYPE_CREATE_ENTRY = "create_entry"
RESULT_TYPE_ABORT = "abort"
RESULT_TYPE_EXTERNAL_STEP = "external"
RESULT_TYPE_EXTERNAL_STEP_DONE = "external_done"

# Event that is fired when a flow is progressed via external source.
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

    def __init__(self, reason: str, description_placeholders: Optional[Dict] = None):
        """Initialize an abort flow exception."""
        super().__init__(f"Flow aborted: {reason}")
        self.reason = reason
        self.description_placeholders = description_placeholders


class FlowManager(abc.ABC):
    """Manage all the flows that are in progress."""

    def __init__(self, hass: HomeAssistant,) -> None:
        """Initialize the flow manager."""
        self.hass = hass
        self._progress: Dict[str, Any] = {}

    @abc.abstractmethod
    async def async_create_flow(
        self,
        handler_key: Any,
        *,
        context: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> "FlowHandler":
        """Create a flow for specified handler.

        Handler key is the domain of the component that we want to set up.
        """

    @abc.abstractmethod
    async def async_finish_flow(
        self, flow: "FlowHandler", result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Finish a config flow and add an entry."""

    async def async_post_init(
        self, flow: "FlowHandler", result: Dict[str, Any]
    ) -> None:
        """Entry has finished executing its first step asynchronously."""

    @callback
    def async_progress(self) -> List[Dict]:
        """Return the flows in progress."""
        return [
            {"flow_id": flow.flow_id, "handler": flow.handler, "context": flow.context}
            for flow in self._progress.values()
            if flow.cur_step is not None
        ]

    async def async_init(
        self, handler: str, *, context: Optional[Dict] = None, data: Any = None
    ) -> Any:
        """Start a configuration flow."""
        if context is None:
            context = {}
        flow = await self.async_create_flow(handler, context=context, data=data)
        if not flow:
            raise UnknownFlow("Flow was not created")
        flow.hass = self.hass
        flow.handler = handler
        flow.flow_id = uuid.uuid4().hex
        flow.context = context
        self._progress[flow.flow_id] = flow

        result = await self._async_handle_step(flow, flow.init_step, data)

        if result["type"] != RESULT_TYPE_ABORT:
            await self.async_post_init(flow, result)

        return result

    async def async_configure(
        self, flow_id: str, user_input: Optional[Dict] = None
    ) -> Any:
        """Continue a configuration flow."""
        flow = self._progress.get(flow_id)

        if flow is None:
            raise UnknownFlow

        cur_step = flow.cur_step

        if cur_step.get("data_schema") is not None and user_input is not None:
            user_input = cur_step["data_schema"](user_input)

        result = await self._async_handle_step(flow, cur_step["step_id"], user_input)

        if cur_step["type"] == RESULT_TYPE_EXTERNAL_STEP:
            if result["type"] not in (
                RESULT_TYPE_EXTERNAL_STEP,
                RESULT_TYPE_EXTERNAL_STEP_DONE,
            ):
                raise ValueError(
                    "External step can only transition to "
                    "external step or external step done."
                )

            # If the result has changed from last result, fire event to update
            # the frontend.
            if cur_step["step_id"] != result.get("step_id"):
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
        self, flow: Any, step_id: str, user_input: Optional[Dict]
    ) -> Dict:
        """Handle a step of a flow."""
        method = f"async_step_{step_id}"

        if not hasattr(flow, method):
            self._progress.pop(flow.flow_id)
            raise UnknownStep(
                f"Handler {flow.__class__.__name__} doesn't support step {step_id}"
            )

        try:
            result: Dict = await getattr(flow, method)(user_input)
        except AbortFlow as err:
            result = _create_abort_data(
                flow.flow_id, flow.handler, err.reason, err.description_placeholders
            )

        if result["type"] not in (
            RESULT_TYPE_FORM,
            RESULT_TYPE_EXTERNAL_STEP,
            RESULT_TYPE_CREATE_ENTRY,
            RESULT_TYPE_ABORT,
            RESULT_TYPE_EXTERNAL_STEP_DONE,
        ):
            raise ValueError(f"Handler returned incorrect type: {result['type']}")

        if result["type"] in (
            RESULT_TYPE_FORM,
            RESULT_TYPE_EXTERNAL_STEP,
            RESULT_TYPE_EXTERNAL_STEP_DONE,
        ):
            flow.cur_step = result
            return result

        # We pass a copy of the result because we're mutating our version
        result = await self.async_finish_flow(flow, dict(result))

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
    flow_id: str = None  # type: ignore
    hass: Optional[HomeAssistant] = None
    handler: Optional[str] = None
    cur_step: Optional[Dict[str, str]] = None
    context: Dict

    # Set by _async_create_flow callback
    init_step = "init"

    # Set by developer
    VERSION = 1

    @callback
    def async_show_form(
        self,
        *,
        step_id: str,
        data_schema: vol.Schema = None,
        errors: Optional[Dict] = None,
        description_placeholders: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Return the definition of a form to gather user input."""
        return {
            "type": RESULT_TYPE_FORM,
            "flow_id": self.flow_id,
            "handler": self.handler,
            "step_id": step_id,
            "data_schema": data_schema,
            "errors": errors,
            "description_placeholders": description_placeholders,
        }

    @callback
    def async_create_entry(
        self,
        *,
        title: str,
        data: Dict,
        description: Optional[str] = None,
        description_placeholders: Optional[Dict] = None,
    ) -> Dict[str, Any]:
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
        self, *, reason: str, description_placeholders: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Abort the config flow."""
        return _create_abort_data(
            self.flow_id, cast(str, self.handler), reason, description_placeholders
        )

    @callback
    def async_external_step(
        self, *, step_id: str, url: str, description_placeholders: Optional[Dict] = None
    ) -> Dict[str, Any]:
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
    def async_external_step_done(self, *, next_step_id: str) -> Dict[str, Any]:
        """Return the definition of an external step for the user to take."""
        return {
            "type": RESULT_TYPE_EXTERNAL_STEP_DONE,
            "flow_id": self.flow_id,
            "handler": self.handler,
            "step_id": next_step_id,
        }


@callback
def _create_abort_data(
    flow_id: str,
    handler: str,
    reason: str,
    description_placeholders: Optional[Dict] = None,
) -> Dict[str, Any]:
    """Return the definition of an external step for the user to take."""
    return {
        "type": RESULT_TYPE_ABORT,
        "flow_id": flow_id,
        "handler": handler,
        "reason": reason,
        "description_placeholders": description_placeholders,
    }
