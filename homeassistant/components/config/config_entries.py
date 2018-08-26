"""Http views to control the config manager."""
import asyncio

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.http import HomeAssistantView
from homeassistant.helpers.data_entry_flow import (
    FlowManagerIndexView, FlowManagerResourceView)


REQUIREMENTS = ['voluptuous-serialize==2.0.0']


@asyncio.coroutine
def async_setup(hass):
    """Enable the Home Assistant views."""
    hass.http.register_view(ConfigManagerEntryIndexView)
    hass.http.register_view(ConfigManagerEntryResourceView)
    hass.http.register_view(
        ConfigManagerFlowIndexView(hass.config_entries.flow))
    hass.http.register_view(
        ConfigManagerFlowResourceView(hass.config_entries.flow))
    hass.http.register_view(ConfigManagerAvailableFlowView)
    return True


def _prepare_json(result):
    """Convert result for JSON."""
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


class ConfigManagerFlowIndexView(FlowManagerIndexView):
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
            flw for flw in hass.config_entries.flow.async_progress()
            if flw['context']['source'] != config_entries.SOURCE_USER])


class ConfigManagerFlowResourceView(FlowManagerResourceView):
    """View to interact with the flow manager."""

    url = '/api/config/config_entries/flow/{flow_id}'
    name = 'api:config:config_entries:flow:resource'


class ConfigManagerAvailableFlowView(HomeAssistantView):
    """View to query available flows."""

    url = '/api/config/config_entries/flow_handlers'
    name = 'api:config:config_entries:flow_handlers'

    @asyncio.coroutine
    def get(self, request):
        """List available flow handlers."""
        return self.json(config_entries.FLOWS)
