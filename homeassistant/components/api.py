import re

import homeassistant as ha
from homeassistant.helpers import TrackStates
import homeassistant.remote as rem
from homeassistant.const import (
    SERVER_PORT, URL_API, URL_API_STATES, URL_API_EVENTS, URL_API_SERVICES,
    URL_API_EVENT_FORWARD, URL_API_STATES_ENTITY, AUTH_HEADER)

HTTP_OK = 200
HTTP_CREATED = 201
HTTP_MOVED_PERMANENTLY = 301
HTTP_BAD_REQUEST = 400
HTTP_UNAUTHORIZED = 401
HTTP_NOT_FOUND = 404
HTTP_METHOD_NOT_ALLOWED = 405
HTTP_UNPROCESSABLE_ENTITY = 422


DOMAIN = 'api'
DEPENDENCIES = ['http']


def setup(hass, config):
    """ """

    if 'http' not in hass.components:
        return False

    # TODO register with hass.http
    # /api - for validation purposes
    hass.http.register_path('GET', URL_API, _handle_get_api)

    # /states
    hass.http.register_path('GET', URL_API_STATES, _handle_get_api_states)
    hass.http.register_path(
        'GET', re.compile(r'/api/states/(?P<entity_id>[a-zA-Z\._0-9]+)'),
        _handle_get_api_states_entity)
    hass.http.register_path(
        'POST', re.compile(r'/api/states/(?P<entity_id>[a-zA-Z\._0-9]+)'),
        _handle_post_state_entity)
    hass.http.register_path(
        'PUT', re.compile(r'/api/states/(?P<entity_id>[a-zA-Z\._0-9]+)'),
        _handle_post_state_entity)

    # /events
    hass.http.register_path('GET', URL_API_EVENTS, _handle_get_api_events)
    hass.http.register_path(
        'POST', re.compile(r'/api/events/(?P<event_type>[a-zA-Z\._0-9]+)'),
        _handle_api_post_events_event)

    # /services
    hass.http.register_path('GET', URL_API_SERVICES, _handle_get_api_services)
    hass.http.register_path(
        'POST',
        re.compile((r'/api/services/'
                    r'(?P<domain>[a-zA-Z\._0-9]+)/'
                    r'(?P<service>[a-zA-Z\._0-9]+)')),
        _handle_post_api_services_domain_service)

    # /event_forwarding
    hass.http.register_path(
        'POST', URL_API_EVENT_FORWARD, _handle_post_api_event_forward)
    hass.http.register_path(
        'DELETE', URL_API_EVENT_FORWARD, _handle_delete_api_event_forward)

    return True

def _handle_get_api(handler, path_match, data):
    """ Renders the debug interface. """
    handler._json_message("API running.")


def _handle_get_api_states(handler, path_match, data):
    """ Returns a dict containing all entity ids and their state. """
    handler._write_json(handler.server.hass.states.all())


def _handle_get_api_states_entity(handler, path_match, data):
    """ Returns the state of a specific entity. """
    entity_id = path_match.group('entity_id')

    state = handler.server.hass.states.get(entity_id)

    if state:
        handler._write_json(state)
    else:
        handler._json_message("State does not exist.", HTTP_NOT_FOUND)


def _handle_post_state_entity(handler, path_match, data):
    """ Handles updating the state of an entity.

    This handles the following paths:
    /api/states/<entity_id>
    """
    entity_id = path_match.group('entity_id')

    try:
        new_state = data['state']
    except KeyError:
        handler._json_message("state not specified", HTTP_BAD_REQUEST)
        return

    attributes = data['attributes'] if 'attributes' in data else None

    is_new_state = handler.server.hass.states.get(entity_id) is None

    # Write state
    handler.server.hass.states.set(entity_id, new_state, attributes)

    state = handler.server.hass.states.get(entity_id)

    status_code = HTTP_CREATED if is_new_state else HTTP_OK

    handler._write_json(
        state.as_dict(),
        status_code=status_code,
        location=URL_API_STATES_ENTITY.format(entity_id))


def _handle_get_api_events(handler, path_match, data):
    """ Handles getting overview of event listeners. """
    handler._write_json([{"event": key, "listener_count": value}
                         for key, value
                         in handler.server.hass.bus.listeners.items()])


def _handle_api_post_events_event(handler, path_match, event_data):
    """ Handles firing of an event.

    This handles the following paths:
    /api/events/<event_type>

    Events from /api are threated as remote events.
    """
    event_type = path_match.group('event_type')

    if event_data is not None and not isinstance(event_data, dict):
        handler._json_message("event_data should be an object",
                              HTTP_UNPROCESSABLE_ENTITY)

    event_origin = ha.EventOrigin.remote

    # Special case handling for event STATE_CHANGED
    # We will try to convert state dicts back to State objects
    if event_type == ha.EVENT_STATE_CHANGED and event_data:
        for key in ('old_state', 'new_state'):
            state = ha.State.from_dict(event_data.get(key))

            if state:
                event_data[key] = state

    handler.server.hass.bus.fire(event_type, event_data, event_origin)

    handler._json_message("Event {} fired.".format(event_type))


def _handle_get_api_services(handler, path_match, data):
    """ Handles getting overview of services. """
    handler._write_json(
        [{"domain": key, "services": value}
         for key, value
         in handler.server.hass.services.services.items()])


# pylint: disable=invalid-name
def _handle_post_api_services_domain_service(handler, path_match, data):
    """ Handles calling a service.

    This handles the following paths:
    /api/services/<domain>/<service>
    """
    domain = path_match.group('domain')
    service = path_match.group('service')

    with TrackStates(handler.server.hass) as changed_states:
        handler.server.hass.services.call(domain, service, data, True)

    handler._write_json(changed_states)


# pylint: disable=invalid-name
def _handle_post_api_event_forward(handler, path_match, data):
    """ Handles adding an event forwarding target. """

    try:
        host = data['host']
        api_password = data['api_password']
    except KeyError:
        handler._json_message("No host or api_password received.",
                              HTTP_BAD_REQUEST)
        return

    try:
        port = int(data['port']) if 'port' in data else None
    except ValueError:
        handler._json_message(
            "Invalid value received for port", HTTP_UNPROCESSABLE_ENTITY)
        return

    api = rem.API(host, api_password, port)

    if not api.validate_api():
        handler._json_message(
            "Unable to validate API", HTTP_UNPROCESSABLE_ENTITY)
        return

    if handler.server.event_forwarder is None:
        handler.server.event_forwarder = \
            rem.EventForwarder(handler.server.hass)

    handler.server.event_forwarder.connect(api)

    handler._json_message("Event forwarding setup.")


def _handle_delete_api_event_forward(handler, path_match, data):
    """ Handles deleting an event forwarding target. """

    try:
        host = data['host']
    except KeyError:
        handler._json_message("No host received.", HTTP_BAD_REQUEST)
        return

    try:
        port = int(data['port']) if 'port' in data else None
    except ValueError:
        handler._json_message(
            "Invalid value received for port", HTTP_UNPROCESSABLE_ENTITY)
        return

    if handler.server.event_forwarder is not None:
        api = rem.API(host, None, port)

        handler.server.event_forwarder.disconnect(api)

    handler._json_message("Event forwarding cancelled.")
