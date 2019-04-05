"""Http views to control the config manager."""

from homeassistant import config_entries, data_entry_flow
from homeassistant.auth.permissions.const import CAT_CONFIG_ENTRIES
from homeassistant.components.http import HomeAssistantView
from homeassistant.exceptions import Unauthorized
from homeassistant.helpers.data_entry_flow import (
    FlowManagerIndexView, FlowManagerResourceView)


async def async_setup(hass):
    """Enable the Home Assistant views."""
    hass.http.register_view(ConfigManagerEntryIndexView)
    hass.http.register_view(ConfigManagerEntryResourceView)
    hass.http.register_view(
        ConfigManagerFlowIndexView(hass.config_entries.flow))
    hass.http.register_view(
        ConfigManagerFlowResourceView(hass.config_entries.flow))
    hass.http.register_view(ConfigManagerAvailableFlowView)
    hass.http.register_view(
        OptionManagerFlowIndexView(hass.config_entries.options.flow))
    hass.http.register_view(
        OptionManagerFlowResourceView(hass.config_entries.options.flow))
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

    async def get(self, request):
        """List available config entries."""
        hass = request.app['hass']

        return self.json([{
            'entry_id': entry.entry_id,
            'domain': entry.domain,
            'title': entry.title,
            'source': entry.source,
            'state': entry.state,
            'connection_class': entry.connection_class,
            'supports_options': hasattr(
                config_entries.HANDLERS[entry.domain],
                'async_get_options_flow'),
        } for entry in hass.config_entries.async_entries()])


class ConfigManagerEntryResourceView(HomeAssistantView):
    """View to interact with a config entry."""

    url = '/api/config/config_entries/entry/{entry_id}'
    name = 'api:config:config_entries:entry:resource'

    async def delete(self, request, entry_id):
        """Delete a config entry."""
        if not request['hass_user'].is_admin:
            raise Unauthorized(config_entry_id=entry_id, permission='remove')

        hass = request.app['hass']

        try:
            result = await hass.config_entries.async_remove(entry_id)
        except config_entries.UnknownEntry:
            return self.json_message('Invalid entry specified', 404)

        return self.json(result)


class ConfigManagerFlowIndexView(FlowManagerIndexView):
    """View to create config flows."""

    url = '/api/config/config_entries/flow'
    name = 'api:config:config_entries:flow'

    async def get(self, request):
        """List flows that are in progress but not started by a user.

        Example of a non-user initiated flow is a discovered Hue hub that
        requires user interaction to finish setup.
        """
        if not request['hass_user'].is_admin:
            raise Unauthorized(
                perm_category=CAT_CONFIG_ENTRIES, permission='add')

        hass = request.app['hass']

        return self.json([
            flw for flw in hass.config_entries.flow.async_progress()
            if flw['context']['source'] != config_entries.SOURCE_USER])

    # pylint: disable=arguments-differ
    async def post(self, request):
        """Handle a POST request."""
        if not request['hass_user'].is_admin:
            raise Unauthorized(
                perm_category=CAT_CONFIG_ENTRIES, permission='add')

        # pylint: disable=no-value-for-parameter
        return await super().post(request)

    def _prepare_result_json(self, result):
        """Convert result to JSON."""
        if result['type'] != data_entry_flow.RESULT_TYPE_CREATE_ENTRY:
            return super()._prepare_result_json(result)

        data = result.copy()
        data['result'] = data['result'].entry_id
        data.pop('data')
        return data


class ConfigManagerFlowResourceView(FlowManagerResourceView):
    """View to interact with the flow manager."""

    url = '/api/config/config_entries/flow/{flow_id}'
    name = 'api:config:config_entries:flow:resource'

    async def get(self, request, flow_id):
        """Get the current state of a data_entry_flow."""
        if not request['hass_user'].is_admin:
            raise Unauthorized(
                perm_category=CAT_CONFIG_ENTRIES, permission='add')

        return await super().get(request, flow_id)

    # pylint: disable=arguments-differ
    async def post(self, request, flow_id):
        """Handle a POST request."""
        if not request['hass_user'].is_admin:
            raise Unauthorized(
                perm_category=CAT_CONFIG_ENTRIES, permission='add')

        # pylint: disable=no-value-for-parameter
        return await super().post(request, flow_id)

    def _prepare_result_json(self, result):
        """Convert result to JSON."""
        if result['type'] != data_entry_flow.RESULT_TYPE_CREATE_ENTRY:
            return super()._prepare_result_json(result)

        data = result.copy()
        data['result'] = data['result'].entry_id
        data.pop('data')
        return data


class ConfigManagerAvailableFlowView(HomeAssistantView):
    """View to query available flows."""

    url = '/api/config/config_entries/flow_handlers'
    name = 'api:config:config_entries:flow_handlers'

    async def get(self, request):
        """List available flow handlers."""
        return self.json(config_entries.FLOWS)


class OptionManagerFlowIndexView(FlowManagerIndexView):
    """View to create option flows."""

    url = '/api/config/config_entries/entry/option/flow'
    name = 'api:config:config_entries:entry:resource:option:flow'

    # pylint: disable=arguments-differ
    async def post(self, request):
        """Handle a POST request.

        handler in request is entry_id.
        """
        if not request['hass_user'].is_admin:
            raise Unauthorized(
                perm_category=CAT_CONFIG_ENTRIES, permission='edit')

        # pylint: disable=no-value-for-parameter
        return await super().post(request)


class OptionManagerFlowResourceView(FlowManagerResourceView):
    """View to interact with the option flow manager."""

    url = '/api/config/config_entries/options/flow/{flow_id}'
    name = 'api:config:config_entries:options:flow:resource'

    async def get(self, request, flow_id):
        """Get the current state of a data_entry_flow."""
        if not request['hass_user'].is_admin:
            raise Unauthorized(
                perm_category=CAT_CONFIG_ENTRIES, permission='edit')

        return await super().get(request, flow_id)

    # pylint: disable=arguments-differ
    async def post(self, request, flow_id):
        """Handle a POST request."""
        if not request['hass_user'].is_admin:
            raise Unauthorized(
                perm_category=CAT_CONFIG_ENTRIES, permission='edit')

        # pylint: disable=no-value-for-parameter
        return await super().post(request, flow_id)
