"""Helpers for the data entry flow."""

import voluptuous as vol

from homeassistant import data_entry_flow, config_entries
from homeassistant.components.http import HomeAssistantView
from homeassistant.components.http.data_validator import RequestDataValidator


class _BaseFlowManagerView(HomeAssistantView):
    """Foundation for flow manager views."""

    def __init__(self, flow_mgr):
        """Initialize the flow manager index view."""
        self._flow_mgr = flow_mgr

    # pylint: disable=no-self-use
    def _prepare_result_json(self, result):
        """Convert result to JSON."""
        if result['type'] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY:
            data = result.copy()
            data.pop('result')
            data.pop('data')
            return data

        if result['type'] != data_entry_flow.RESULT_TYPE_FORM:
            return result

        import voluptuous_serialize

        data = result.copy()

        schema = data['data_schema']
        if schema is None:
            data['data_schema'] = []
        else:
            data['data_schema'] = voluptuous_serialize.convert(schema)

        return data


class FlowManagerIndexView(_BaseFlowManagerView):
    """View to create config flows."""

    @RequestDataValidator(vol.Schema({
        vol.Required('handler'): vol.Any(str, list),
    }, extra=vol.ALLOW_EXTRA))
    async def post(self, request, data):
        """Handle a POST request."""
        if isinstance(data['handler'], list):
            handler = tuple(data['handler'])
        else:
            handler = data['handler']

        try:
            result = await self._flow_mgr.async_init(
                handler, context={'source': config_entries.SOURCE_USER})
        except data_entry_flow.UnknownHandler:
            return self.json_message('Invalid handler specified', 404)
        except data_entry_flow.UnknownStep:
            return self.json_message('Handler does not support init', 400)

        result = self._prepare_result_json(result)

        return self.json(result)


class FlowManagerResourceView(_BaseFlowManagerView):
    """View to interact with the flow manager."""

    async def get(self, request, flow_id):
        """Get the current state of a data_entry_flow."""
        try:
            result = await self._flow_mgr.async_configure(flow_id)
        except data_entry_flow.UnknownFlow:
            return self.json_message('Invalid flow specified', 404)

        result = self._prepare_result_json(result)

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

        result = self._prepare_result_json(result)

        return self.json(result)

    async def delete(self, request, flow_id):
        """Cancel a flow in progress."""
        try:
            self._flow_mgr.async_abort(flow_id)
        except data_entry_flow.UnknownFlow:
            return self.json_message('Invalid flow specified', 404)

        return self.json_message('Flow aborted')
