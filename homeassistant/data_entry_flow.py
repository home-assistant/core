"""Classes to help gather user submissions."""
import logging
from typing import Dict, Any, Callable, Hashable, List, Optional  # noqa pylint: disable=unused-import
import uuid
import voluptuous as vol
from .core import callback, HomeAssistant
from .exceptions import HomeAssistantError

_LOGGER = logging.getLogger(__name__)

RESULT_TYPE_FORM = 'form'
RESULT_TYPE_CREATE_ENTRY = 'create_entry'
RESULT_TYPE_ABORT = 'abort'


class FlowError(HomeAssistantError):
    """Error while configuring an account."""


class UnknownHandler(FlowError):
    """Unknown handler specified."""


class UnknownFlow(FlowError):
    """Uknown flow specified."""


class UnknownStep(FlowError):
    """Unknown step specified."""


class FlowManager:
    """Manage all the flows that are in progress."""

    def __init__(self, hass: HomeAssistant, async_create_flow: Callable,
                 async_finish_flow: Callable) -> None:
        """Initialize the flow manager."""
        self.hass = hass
        self._progress = {}  # type: Dict[str, Any]
        self._async_create_flow = async_create_flow
        self._async_finish_flow = async_finish_flow

    @callback
    def async_progress(self) -> List[Dict]:
        """Return the flows in progress."""
        return [{
            'flow_id': flow.flow_id,
            'handler': flow.handler,
            'context': flow.context,
        } for flow in self._progress.values()]

    async def async_init(self, handler: Hashable, *,
                         context: Optional[Dict] = None,
                         data: Any = None) -> Any:
        """Start a configuration flow."""
        flow = await self._async_create_flow(
            handler, context=context, data=data)
        flow.hass = self.hass
        flow.handler = handler
        flow.flow_id = uuid.uuid4().hex
        flow.context = context
        self._progress[flow.flow_id] = flow

        return await self._async_handle_step(flow, flow.init_step, data)

    async def async_configure(
            self, flow_id: str, user_input: Optional[Dict] = None) -> Any:
        """Continue a configuration flow."""
        flow = self._progress.get(flow_id)

        if flow is None:
            raise UnknownFlow

        step_id, data_schema = flow.cur_step

        if data_schema is not None and user_input is not None:
            user_input = data_schema(user_input)

        return await self._async_handle_step(
            flow, step_id, user_input)

    @callback
    def async_abort(self, flow_id: str) -> None:
        """Abort a flow."""
        if self._progress.pop(flow_id, None) is None:
            raise UnknownFlow

    async def _async_handle_step(self, flow: Any, step_id: str,
                                 user_input: Optional[Dict]) -> Dict:
        """Handle a step of a flow."""
        method = "async_step_{}".format(step_id)

        if not hasattr(flow, method):
            self._progress.pop(flow.flow_id)
            raise UnknownStep("Handler {} doesn't support step {}".format(
                flow.__class__.__name__, step_id))

        result = await getattr(flow, method)(user_input)  # type: Dict

        if result['type'] not in (RESULT_TYPE_FORM, RESULT_TYPE_CREATE_ENTRY,
                                  RESULT_TYPE_ABORT):
            raise ValueError(
                'Handler returned incorrect type: {}'.format(result['type']))

        if result['type'] == RESULT_TYPE_FORM:
            flow.cur_step = (result['step_id'], result['data_schema'])
            return result

        # We pass a copy of the result because we're mutating our version
        result = await self._async_finish_flow(flow, dict(result))

        # _async_finish_flow may change result type, check it again
        if result['type'] == RESULT_TYPE_FORM:
            flow.cur_step = (result['step_id'], result['data_schema'])
            return result

        # Abort and Success results both finish the flow
        self._progress.pop(flow.flow_id)

        return result


class FlowHandler:
    """Handle the configuration flow of a component."""

    # Set by flow manager
    flow_id = None
    hass = None
    handler = None
    cur_step = None
    context = None

    # Set by _async_create_flow callback
    init_step = 'init'

    # Set by developer
    VERSION = 1

    @callback
    def async_show_form(self, *, step_id: str, data_schema: vol.Schema = None,
                        errors: Optional[Dict] = None,
                        description_placeholders: Optional[Dict] = None) \
            -> Dict:
        """Return the definition of a form to gather user input."""
        return {
            'type': RESULT_TYPE_FORM,
            'flow_id': self.flow_id,
            'handler': self.handler,
            'step_id': step_id,
            'data_schema': data_schema,
            'errors': errors,
            'description_placeholders': description_placeholders,
        }

    @callback
    def async_create_entry(self, *, title: str, data: Dict,
                           description: Optional[str] = None,
                           description_placeholders: Optional[Dict] = None) \
            -> Dict:
        """Finish config flow and create a config entry."""
        return {
            'version': self.VERSION,
            'type': RESULT_TYPE_CREATE_ENTRY,
            'flow_id': self.flow_id,
            'handler': self.handler,
            'title': title,
            'data': data,
            'description': description,
            'description_placeholders': description_placeholders,
        }

    @callback
    def async_abort(self, *, reason: str) -> Dict:
        """Abort the config flow."""
        return {
            'type': RESULT_TYPE_ABORT,
            'flow_id': self.flow_id,
            'handler': self.handler,
            'reason': reason
        }
