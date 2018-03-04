"""Http views to control the config manager."""
import asyncio

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.http import HomeAssistantView
from homeassistant.components.http.data_validator import RequestDataValidator


REQUIREMENTS = ['voluptuous-serialize==1']


@asyncio.coroutine
def async_setup(hass):
    """Enable the Home Assistant views."""
    hass.http.register_view(ConfigManagerEntryIndexView)
    hass.http.register_view(ConfigManagerEntryResourceView)
    hass.http.register_view(ConfigManagerFlowIndexView)
    hass.http.register_view(ConfigManagerFlowResourceView)
    hass.http.register_view(ConfigManagerAvailableFlowView)
    return True


def _prepare_json(result):
    """Convert result for JSON."""
    if result['type'] != config_entries.RESULT_TYPE_FORM:
        return result

    import voluptuous_serialize

    data = result.copy()

    schema = data['data_schema']
    if schema is None:
        data['data_schema'] = []
    else:
        data['data_schema'] = voluptuous_serialize.convert(schema)

    return data


class ConfigManagerEntryIndexView(HomeAssistantView):
    """View to get available config entries."""

    url = '/api/config/config_entries/entry'
    name = 'api:config:config_entries:entry'

    @asyncio.coroutine
    def get(self, request):
        """List flows in progress."""
        hass = request.app['hass']
        return self.json([{
            'entry_id': entry.entry_id,
            'domain': entry.domain,
            'title': entry.title,
            'source': entry.source,
            'state': entry.state,
        } for entry in hass.config_entries.async_entries()])


class ConfigManagerEntryResourceView(HomeAssistantView):
    """View to interact with a config entry."""

    url = '/api/config/config_entries/entry/{entry_id}'
    name = 'api:config:config_entries:entry:resource'

    @asyncio.coroutine
    def delete(self, request, entry_id):
        """Delete a config entry."""
        hass = request.app['hass']

        try:
            result = yield from hass.config_entries.async_remove(entry_id)
        except config_entries.UnknownEntry:
            return self.json_message('Invalid entry specified', 404)

        return self.json(result)


class ConfigManagerFlowIndexView(HomeAssistantView):
    """View to create config flows."""

    url = '/api/config/config_entries/flow'
    name = 'api:config:config_entries:flow'

    @asyncio.coroutine
    def get(self, request):
        """List flows that are in progress but not started by a user.

        Example of a non-user initiated flow is a discovered Hue hub that
        requires user interaction to finish setup.
        """
        hass = request.app['hass']

        return self.json([
            flow for flow in hass.config_entries.flow.async_progress()
            if flow['source'] != config_entries.SOURCE_USER])

    @RequestDataValidator(vol.Schema({
        vol.Required('domain'): str,
    }))
    @asyncio.coroutine
    def post(self, request, data):
        """Handle a POST request."""
        hass = request.app['hass']

        try:
            result = yield from hass.config_entries.flow.async_init(
                data['domain'])
        except config_entries.UnknownHandler:
            return self.json_message('Invalid handler specified', 404)
        except config_entries.UnknownStep:
            return self.json_message('Handler does not support init', 400)

        result = _prepare_json(result)

        return self.json(result)


class ConfigManagerFlowResourceView(HomeAssistantView):
    """View to interact with the flow manager."""

    url = '/api/config/config_entries/flow/{flow_id}'
    name = 'api:config:config_entries:flow:resource'

    @asyncio.coroutine
    def get(self, request, flow_id):
        """Get the current state of a flow."""
        hass = request.app['hass']

        try:
            result = yield from hass.config_entries.flow.async_configure(
                flow_id)
        except config_entries.UnknownFlow:
            return self.json_message('Invalid flow specified', 404)

        result = _prepare_json(result)

        return self.json(result)

    @RequestDataValidator(vol.Schema(dict), allow_empty=True)
    @asyncio.coroutine
    def post(self, request, flow_id, data):
        """Handle a POST request."""
        hass = request.app['hass']

        try:
            result = yield from hass.config_entries.flow.async_configure(
                flow_id, data)
        except config_entries.UnknownFlow:
            return self.json_message('Invalid flow specified', 404)
        except vol.Invalid:
            return self.json_message('User input malformed', 400)

        result = _prepare_json(result)

        return self.json(result)

    @asyncio.coroutine
    def delete(self, request, flow_id):
        """Cancel a flow in progress."""
        hass = request.app['hass']

        try:
            hass.config_entries.flow.async_abort(flow_id)
        except config_entries.UnknownFlow:
            return self.json_message('Invalid flow specified', 404)

        return self.json_message('Flow aborted')


class ConfigManagerAvailableFlowView(HomeAssistantView):
    """View to query available flows."""

    url = '/api/config/config_entries/flow_handlers'
    name = 'api:config:config_entries:flow_handlers'

    @asyncio.coroutine
    def get(self, request):
        """List available flow handlers."""
        return self.json(config_entries.FLOWS)
