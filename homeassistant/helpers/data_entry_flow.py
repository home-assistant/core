"""Helpers for the data entry flow."""

import voluptuous as vol

from homeassistant import data_entry_flow
from homeassistant.components.http import HomeAssistantView
from homeassistant.components.http.data_validator import RequestDataValidator


def _prepare_json(result):
    """Convert result for JSON."""
    if result['type'] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY:
        data = result.copy()
        data.pop('result')
        data.pop('data')
        return data

    elif result['type'] != data_entry_flow.RESULT_TYPE_FORM:
        return result

    import voluptuous_serialize

    data = result.copy()

    schema = data['data_schema']
    if schema is None:
        data['data_schema'] = []
    else:
        data['data_schema'] = voluptuous_serialize.convert(schema)

    return data


class FlowManagerIndexView(HomeAssistantView):
    """View to create config flows."""

    def __init__(self, flow_mgr):
        """Initialize the flow manager index view."""
        self._flow_mgr = flow_mgr

    async def get(self, request):
        """List flows that are in progress."""
        return self.json(self._flow_mgr.async_progress())

    @RequestDataValidator(vol.Schema({
        vol.Required('handler'): vol.Any(str, list),
    }))
    async def post(self, request, data):
        """Handle a POST request."""
        if isinstance(data['handler'], list):
            handler = tuple(data['handler'])
        else:
            handler = data['handler']

        try:
            result = await self._flow_mgr.async_init(handler)
        except data_entry_flow.UnknownHandler:
            return self.json_message('Invalid handler specified', 404)
        except data_entry_flow.UnknownStep:
            return self.json_message('Handler does not support init', 400)

        result = _prepare_json(result)

        return self.json(result)


class FlowManagerResourceView(HomeAssistantView):
    """View to interact with the flow manager."""

    def __init__(self, flow_mgr):
        """Initialize the flow manager resource view."""
        self._flow_mgr = flow_mgr

    async def get(self, request, flow_id):
        """Get the current state of a data_entry_flow."""
        try:
            result = await self._flow_mgr.async_configure(flow_id)
        except data_entry_flow.UnknownFlow:
            return self.json_message('Invalid flow specified', 404)

        result = _prepare_json(result)

        return self.json(result)

    @RequestDataValidator(vol.Schema(dict), allow_empty=True)
    async def post(self, request, flow_id, data):
        """Handle a POST request."""
        try:
            result = await self._flow_mgr.async_configure(flow_id, data)
        except data_entry_flow.UnknownFlow:
            return self.json_message('Invalid flow specified', 404)
        except vol.Invalid:
            return self.json_message('User input malformed', 400)

        result = _prepare_json(result)

        return self.json(result)

    async def delete(self, request, flow_id):
        """Cancel a flow in progress."""
        try:
            self._flow_mgr.async_abort(flow_id)
        except data_entry_flow.UnknownFlow:
            return self.json_message('Invalid flow specified', 404)

        return self.json_message('Flow aborted')
