"""
Rest API for Home Assistant.

For more details about the RESTful API, please refer to the documentation at
https://developers.home-assistant.io/docs/en/external_api_rest.html
"""
import asyncio
import json
import logging

from aiohttp import web
import async_timeout

from homeassistant.bootstrap import DATA_LOGGING
from homeassistant.components.http import HomeAssistantView
from homeassistant.const import (
    EVENT_HOMEASSISTANT_STOP, EVENT_TIME_CHANGED, HTTP_BAD_REQUEST,
    HTTP_CREATED, HTTP_NOT_FOUND, MATCH_ALL, URL_API, URL_API_COMPONENTS,
    URL_API_CONFIG, URL_API_DISCOVERY_INFO, URL_API_ERROR_LOG, URL_API_EVENTS,
    URL_API_SERVICES, URL_API_STATES, URL_API_STATES_ENTITY, URL_API_STREAM,
    URL_API_TEMPLATE, __version__)
import homeassistant.core as ha
from homeassistant.exceptions import TemplateError
from homeassistant.helpers import template
from homeassistant.helpers.service import async_get_all_descriptions
from homeassistant.helpers.state import AsyncTrackStates
import homeassistant.remote as rem

_LOGGER = logging.getLogger(__name__)

ATTR_BASE_URL = 'base_url'
ATTR_LOCATION_NAME = 'location_name'
ATTR_REQUIRES_API_PASSWORD = 'requires_api_password'
ATTR_VERSION = 'version'

DOMAIN = 'api'
DEPENDENCIES = ['http']

STREAM_PING_PAYLOAD = 'ping'
STREAM_PING_INTERVAL = 50  # seconds


def setup(hass, config):
    """Register the API with the HTTP interface."""
    hass.http.register_view(APIStatusView)
    hass.http.register_view(APIEventStream)
    hass.http.register_view(APIConfigView)
    hass.http.register_view(APIDiscoveryView)
    hass.http.register_view(APIStatesView)
    hass.http.register_view(APIEntityStateView)
    hass.http.register_view(APIEventListenersView)
    hass.http.register_view(APIEventView)
    hass.http.register_view(APIServicesView)
    hass.http.register_view(APIDomainServicesView)
    hass.http.register_view(APIComponentsView)
    hass.http.register_view(APITemplateView)

    if DATA_LOGGING in hass.data:
        hass.http.register_view(APIErrorLog)

    return True


class APIStatusView(HomeAssistantView):
    """View to handle Status requests."""

    url = URL_API
    name = 'api:status'

    @ha.callback
    def get(self, request):
        """Retrieve if API is running."""
        return self.json_message("API running.")


class APIEventStream(HomeAssistantView):
    """View to handle EventStream requests."""

    url = URL_API_STREAM
    name = 'api:stream'

    async def get(self, request):
        """Provide a streaming interface for the event bus."""
        hass = request.app['hass']
        stop_obj = object()
        to_write = asyncio.Queue(loop=hass.loop)

        restrict = request.query.get('restrict')
        if restrict:
            restrict = restrict.split(',') + [EVENT_HOMEASSISTANT_STOP]

        async def forward_events(event):
            """Forward events to the open request."""
            if event.event_type == EVENT_TIME_CHANGED:
                return

            if restrict and event.event_type not in restrict:
                return

            _LOGGER.debug("STREAM %s FORWARDING %s", id(stop_obj), event)

            if event.event_type == EVENT_HOMEASSISTANT_STOP:
                data = stop_obj
            else:
                data = json.dumps(event, cls=rem.JSONEncoder)

            await to_write.put(data)

        response = web.StreamResponse()
        response.content_type = 'text/event-stream'
        await response.prepare(request)

        unsub_stream = hass.bus.async_listen(MATCH_ALL, forward_events)

        try:
            _LOGGER.debug("STREAM %s ATTACHED", id(stop_obj))

            # Fire off one message so browsers fire open event right away
            await to_write.put(STREAM_PING_PAYLOAD)

            while True:
                try:
                    with async_timeout.timeout(STREAM_PING_INTERVAL,
                                               loop=hass.loop):
                        payload = await to_write.get()

                    if payload is stop_obj:
                        break

                    msg = "data: {}\n\n".format(payload)
                    _LOGGER.debug(
                        "STREAM %s WRITING %s", id(stop_obj), msg.strip())
                    await response.write(msg.encode('UTF-8'))
                except asyncio.TimeoutError:
                    await to_write.put(STREAM_PING_PAYLOAD)

        except asyncio.CancelledError:
            _LOGGER.debug("STREAM %s ABORT", id(stop_obj))

        finally:
            _LOGGER.debug("STREAM %s RESPONSE CLOSED", id(stop_obj))
            unsub_stream()


class APIConfigView(HomeAssistantView):
    """View to handle Configuration requests."""

    url = URL_API_CONFIG
    name = 'api:config'

    @ha.callback
    def get(self, request):
        """Get current configuration."""
        return self.json(request.app['hass'].config.as_dict())


class APIDiscoveryView(HomeAssistantView):
    """View to provide Discovery information."""

    requires_auth = False
    url = URL_API_DISCOVERY_INFO
    name = 'api:discovery'

    @ha.callback
    def get(self, request):
        """Get discovery information."""
        hass = request.app['hass']
        needs_auth = hass.config.api.api_password is not None
        return self.json({
            ATTR_BASE_URL: hass.config.api.base_url,
            ATTR_LOCATION_NAME: hass.config.location_name,
            ATTR_REQUIRES_API_PASSWORD: needs_auth,
            ATTR_VERSION: __version__,
        })


class APIStatesView(HomeAssistantView):
    """View to handle States requests."""

    url = URL_API_STATES
    name = "api:states"

    @ha.callback
    def get(self, request):
        """Get current states."""
        return self.json(request.app['hass'].states.async_all())


class APIEntityStateView(HomeAssistantView):
    """View to handle EntityState requests."""

    url = '/api/states/{entity_id}'
    name = 'api:entity-state'

    @ha.callback
    def get(self, request, entity_id):
        """Retrieve state of entity."""
        state = request.app['hass'].states.get(entity_id)
        if state:
            return self.json(state)
        return self.json_message("Entity not found.", HTTP_NOT_FOUND)

    async def post(self, request, entity_id):
        """Update state of entity."""
        hass = request.app['hass']
        try:
            data = await request.json()
        except ValueError:
            return self.json_message(
                "Invalid JSON specified.", HTTP_BAD_REQUEST)

        new_state = data.get('state')

        if new_state is None:
            return self.json_message("No state specified.", HTTP_BAD_REQUEST)

        attributes = data.get('attributes')
        force_update = data.get('force_update', False)

        is_new_state = hass.states.get(entity_id) is None

        # Write state
        hass.states.async_set(entity_id, new_state, attributes, force_update,
                              self.context(request))

        # Read the state back for our response
        status_code = HTTP_CREATED if is_new_state else 200
        resp = self.json(hass.states.get(entity_id), status_code)

        resp.headers.add('Location', URL_API_STATES_ENTITY.format(entity_id))

        return resp

    @ha.callback
    def delete(self, request, entity_id):
        """Remove entity."""
        if request.app['hass'].states.async_remove(entity_id):
            return self.json_message("Entity removed.")
        return self.json_message("Entity not found.", HTTP_NOT_FOUND)


class APIEventListenersView(HomeAssistantView):
    """View to handle EventListeners requests."""

    url = URL_API_EVENTS
    name = 'api:event-listeners'

    @ha.callback
    def get(self, request):
        """Get event listeners."""
        return self.json(async_events_json(request.app['hass']))


class APIEventView(HomeAssistantView):
    """View to handle Event requests."""

    url = '/api/events/{event_type}'
    name = 'api:event'

    async def post(self, request, event_type):
        """Fire events."""
        body = await request.text()
        try:
            event_data = json.loads(body) if body else None
        except ValueError:
            return self.json_message(
                "Event data should be valid JSON.", HTTP_BAD_REQUEST)

        if event_data is not None and not isinstance(event_data, dict):
            return self.json_message(
                "Event data should be a JSON object", HTTP_BAD_REQUEST)

        # Special case handling for event STATE_CHANGED
        # We will try to convert state dicts back to State objects
        if event_type == ha.EVENT_STATE_CHANGED and event_data:
            for key in ('old_state', 'new_state'):
                state = ha.State.from_dict(event_data.get(key))

                if state:
                    event_data[key] = state

        request.app['hass'].bus.async_fire(
            event_type, event_data, ha.EventOrigin.remote,
            self.context(request))

        return self.json_message("Event {} fired.".format(event_type))


class APIServicesView(HomeAssistantView):
    """View to handle Services requests."""

    url = URL_API_SERVICES
    name = 'api:services'

    async def get(self, request):
        """Get registered services."""
        services = await async_services_json(request.app['hass'])
        return self.json(services)


class APIDomainServicesView(HomeAssistantView):
    """View to handle DomainServices requests."""

    url = '/api/services/{domain}/{service}'
    name = 'api:domain-services'

    async def post(self, request, domain, service):
        """Call a service.

        Returns a list of changed states.
        """
        hass = request.app['hass']
        body = await request.text()
        try:
            data = json.loads(body) if body else None
        except ValueError:
            return self.json_message(
                "Data should be valid JSON.", HTTP_BAD_REQUEST)

        with AsyncTrackStates(hass) as changed_states:
            await hass.services.async_call(
                domain, service, data, True, self.context(request))

        return self.json(changed_states)


class APIComponentsView(HomeAssistantView):
    """View to handle Components requests."""

    url = URL_API_COMPONENTS
    name = 'api:components'

    @ha.callback
    def get(self, request):
        """Get current loaded components."""
        return self.json(request.app['hass'].config.components)


class APITemplateView(HomeAssistantView):
    """View to handle Template requests."""

    url = URL_API_TEMPLATE
    name = 'api:template'

    async def post(self, request):
        """Render a template."""
        try:
            data = await request.json()
            tpl = template.Template(data['template'], request.app['hass'])
            return tpl.async_render(data.get('variables'))
        except (ValueError, TemplateError) as ex:
            return self.json_message(
                "Error rendering template: {}".format(ex), HTTP_BAD_REQUEST)


class APIErrorLog(HomeAssistantView):
    """View to fetch the API error log."""

    url = URL_API_ERROR_LOG
    name = 'api:error_log'

    async def get(self, request):
        """Retrieve API error log."""
        return web.FileResponse(request.app['hass'].data[DATA_LOGGING])


async def async_services_json(hass):
    """Generate services data to JSONify."""
    descriptions = await async_get_all_descriptions(hass)
    return [{'domain': key, 'services': value}
            for key, value in descriptions.items()]


def async_events_json(hass):
    """Generate event data to JSONify."""
    return [{'event': key, 'listener_count': value}
            for key, value in hass.bus.async_listeners().items()]
