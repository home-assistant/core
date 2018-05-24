"""Classes to help gather user submissions."""
import logging
import uuid

from .core import callback
from .exceptions import HomeAssistantError

_LOGGER = logging.getLogger(__name__)

SOURCE_USER = 'user'
SOURCE_DISCOVERY = 'discovery'

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

    def __init__(self, hass, async_create_flow, async_finish_flow):
        """Initialize the flow manager."""
        self.hass = hass
        self._progress = {}
        self._async_create_flow = async_create_flow
        self._async_finish_flow = async_finish_flow

    @callback
    def async_progress(self):
        """Return the flows in progress."""
        return [{
            'flow_id': flow.flow_id,
            'handler': flow.handler,
            'source': flow.source,
        } for flow in self._progress.values()]

    async def async_init(self, handler, *, source=SOURCE_USER, data=None):
        """Start a configuration flow."""
        flow = await self._async_create_flow(handler, source=source, data=data)
        flow.hass = self.hass
        flow.handler = handler
        flow.flow_id = uuid.uuid4().hex
        flow.source = source
        self._progress[flow.flow_id] = flow

        if source == SOURCE_USER:
            step = 'init'
        else:
            step = source

        return await self._async_handle_step(flow, step, data)

    async def async_configure(self, flow_id, user_input=None):
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
    def async_abort(self, flow_id):
        """Abort a flow."""
        if self._progress.pop(flow_id, None) is None:
            raise UnknownFlow

    async def _async_handle_step(self, flow, step_id, user_input):
        """Handle a step of a flow."""
        method = "async_step_{}".format(step_id)

        if not hasattr(flow, method):
            self._progress.pop(flow.flow_id)
            raise UnknownStep("Handler {} doesn't support step {}".format(
                flow.__class__.__name__, step_id))

        result = await getattr(flow, method)(user_input)

        if result['type'] not in (RESULT_TYPE_FORM, RESULT_TYPE_CREATE_ENTRY,
                                  RESULT_TYPE_ABORT):
            raise ValueError(
                'Handler returned incorrect type: {}'.format(result['type']))

        if result['type'] == RESULT_TYPE_FORM:
            flow.cur_step = (result['step_id'], result['data_schema'])
            return result

        # Abort and Success results both finish the flow
        self._progress.pop(flow.flow_id)

        # We pass a copy of the result because we're mutating our version
        entry = await self._async_finish_flow(dict(result))

        if result['type'] == RESULT_TYPE_CREATE_ENTRY:
            result['result'] = entry
        return result


class FlowHandler:
    """Handle the configuration flow of a component."""

    # Set by flow manager
    flow_id = None
    hass = None
    handler = None
    source = SOURCE_USER
    cur_step = None

    # Set by developer
    VERSION = 1

    @callback
    def async_show_form(self, *, step_id, data_schema=None, errors=None):
        """Return the definition of a form to gather user input."""
        return {
            'type': RESULT_TYPE_FORM,
            'flow_id': self.flow_id,
            'handler': self.handler,
            'step_id': step_id,
            'data_schema': data_schema,
            'errors': errors,
        }

    @callback
    def async_create_entry(self, *, title, data):
        """Finish config flow and create a config entry."""
        return {
            'version': self.VERSION,
            'type': RESULT_TYPE_CREATE_ENTRY,
            'flow_id': self.flow_id,
            'handler': self.handler,
            'title': title,
            'data': data,
            'source': self.source,
        }

    @callback
    def async_abort(self, *, reason):
        """Abort the config flow."""
        return {
            'type': RESULT_TYPE_ABORT,
            'flow_id': self.flow_id,
            'handler': self.handler,
            'reason': reason
        }
