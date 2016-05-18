"""
Rest API for Home Assistant.

For more details about the RESTful API, please refer to the documentation at
https://home-assistant.io/developers/api/
"""
import json
import logging
import re
import threading

import homeassistant.core as ha
import homeassistant.remote as rem
from homeassistant.bootstrap import ERROR_LOG_FILENAME
from homeassistant.const import (
    CONTENT_TYPE_TEXT_PLAIN, EVENT_HOMEASSISTANT_STOP, EVENT_TIME_CHANGED,
    HTTP_BAD_REQUEST, HTTP_CREATED, HTTP_HEADER_CONTENT_TYPE, HTTP_NOT_FOUND,
    HTTP_OK, HTTP_UNPROCESSABLE_ENTITY, MATCH_ALL, URL_API, URL_API_COMPONENTS,
    URL_API_CONFIG, URL_API_DISCOVERY_INFO, URL_API_ERROR_LOG,
    URL_API_EVENT_FORWARD, URL_API_EVENTS, URL_API_LOG_OUT, URL_API_SERVICES,
    URL_API_STATES, URL_API_STATES_ENTITY, URL_API_STREAM, URL_API_TEMPLATE,
    __version__)
from homeassistant.exceptions import TemplateError
from homeassistant.helpers.state import TrackStates
from homeassistant.helpers import template

DOMAIN = 'api'
DEPENDENCIES = ['http']

STREAM_PING_PAYLOAD = "ping"
STREAM_PING_INTERVAL = 50  # seconds

_LOGGER = logging.getLogger(__name__)


def setup(hass, config):
    """Register the API with the HTTP interface."""
    # /api - for validation purposes
    hass.http.register_path('GET', URL_API, _handle_get_api)

    # /api/config
    hass.http.register_path('GET', URL_API_CONFIG, _handle_get_api_config)

    # /api/discovery_info
    hass.http.register_path('GET', URL_API_DISCOVERY_INFO,
                            _handle_get_api_discovery_info,
                            require_auth=False)

    # /api/stream
    hass.http.register_path('GET', URL_API_STREAM, _handle_get_api_stream)

    # /api/states
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
    hass.http.register_path(
        'DELETE', re.compile(r'/api/states/(?P<entity_id>[a-zA-Z\._0-9]+)'),
        _handle_delete_state_entity)

    # /api/events
    hass.http.register_path('GET', URL_API_EVENTS, _handle_get_api_events)
    hass.http.register_path(
        'POST', re.compile(r'/api/events/(?P<event_type>[a-zA-Z\._0-9]+)'),
        _handle_api_post_events_event)

    # /api/services
    hass.http.register_path('GET', URL_API_SERVICES, _handle_get_api_services)
    hass.http.register_path(
        'POST',
        re.compile((r'/api/services/'
                    r'(?P<domain>[a-zA-Z\._0-9]+)/'
                    r'(?P<service>[a-zA-Z\._0-9]+)')),
        _handle_post_api_services_domain_service)

    # /api/event_forwarding
    hass.http.register_path(
        'POST', URL_API_EVENT_FORWARD, _handle_post_api_event_forward)
    hass.http.register_path(
        'DELETE', URL_API_EVENT_FORWARD, _handle_delete_api_event_forward)

    # /api/components
    hass.http.register_path(
        'GET', URL_API_COMPONENTS, _handle_get_api_components)

    # /api/error_log
    hass.http.register_path('GET', URL_API_ERROR_LOG,
                            _handle_get_api_error_log)

    hass.http.register_path('POST', URL_API_LOG_OUT, _handle_post_api_log_out)

    # /api/template
    hass.http.register_path('POST', URL_API_TEMPLATE,
                            _handle_post_api_template)

    return True


def _handle_get_api(handler, path_match, data):
    """Render the debug interface."""
    handler.write_json_message("API running.")


def _handle_get_api_stream(handler, path_match, data):
    """Provide a streaming interface for the event bus."""
    gracefully_closed = False
    hass = handler.server.hass
    wfile = handler.wfile
    write_lock = threading.Lock()
    block = threading.Event()
    session_id = None

    restrict = data.get('restrict')
    if restrict:
        restrict = restrict.split(',')

    def write_message(payload):
        """Write a message to the output."""
        with write_lock:
            msg = "data: {}\n\n".format(payload)

            try:
                wfile.write(msg.encode("UTF-8"))
                wfile.flush()
            except (IOError, ValueError):
                # IOError: socket errors
                # ValueError: raised when 'I/O operation on closed file'
                block.set()

    def forward_events(event):
        """Forward events to the open request."""
        nonlocal gracefully_closed

        if block.is_set() or event.event_type == EVENT_TIME_CHANGED:
            return
        elif event.event_type == EVENT_HOMEASSISTANT_STOP:
            gracefully_closed = True
            block.set()
            return

        handler.server.sessions.extend_validation(session_id)
        write_message(json.dumps(event, cls=rem.JSONEncoder))

    handler.send_response(HTTP_OK)
    handler.send_header('Content-type', 'text/event-stream')
    session_id = handler.set_session_cookie_header()
    handler.end_headers()

    if restrict:
        for event in restrict:
            hass.bus.listen(event, forward_events)
    else:
        hass.bus.listen(MATCH_ALL, forward_events)

    while True:
        write_message(STREAM_PING_PAYLOAD)

        block.wait(STREAM_PING_INTERVAL)

        if block.is_set():
            break

    if not gracefully_closed:
        _LOGGER.info("Found broken event stream to %s, cleaning up",
                     handler.client_address[0])

    if restrict:
        for event in restrict:
            hass.bus.remove_listener(event, forward_events)
    else:
        hass.bus.remove_listener(MATCH_ALL, forward_events)


def _handle_get_api_config(handler, path_match, data):
    """Return the Home Assistant configuration."""
    handler.write_json(handler.server.hass.config.as_dict())


def _handle_get_api_discovery_info(handler, path_match, data):
    needs_auth = (handler.server.hass.config.api.api_password is not None)
    params = {
        'base_url': handler.server.hass.config.api.base_url,
        'location_name': handler.server.hass.config.location_name,
        'requires_api_password': needs_auth,
        'version': __version__
    }
    handler.write_json(params)


def _handle_get_api_states(handler, path_match, data):
    """Return a dict containing all entity ids and their state."""
    handler.write_json(handler.server.hass.states.all())


def _handle_get_api_states_entity(handler, path_match, data):
    """Return the state of a specific entity."""
    entity_id = path_match.group('entity_id')

    state = handler.server.hass.states.get(entity_id)

    if state:
        handler.write_json(state)
    else:
        handler.write_json_message("State does not exist.", HTTP_NOT_FOUND)


def _handle_post_state_entity(handler, path_match, data):
    """Handle updating the state of an entity.

    This handles the following paths:
    /api/states/<entity_id>
    """
    entity_id = path_match.group('entity_id')

    try:
        new_state = data['state']
    except KeyError:
        handler.write_json_message("state not specified", HTTP_BAD_REQUEST)
        return

    attributes = data['attributes'] if 'attributes' in data else None

    is_new_state = handler.server.hass.states.get(entity_id) is None

    # Write state
    handler.server.hass.states.set(entity_id, new_state, attributes)

    state = handler.server.hass.states.get(entity_id)

    status_code = HTTP_CREATED if is_new_state else HTTP_OK

    handler.write_json(
        state.as_dict(),
        status_code=status_code,
        location=URL_API_STATES_ENTITY.format(entity_id))


def _handle_delete_state_entity(handler, path_match, data):
    """Handle request to delete an entity from state machine.

    This handles the following paths:
    /api/states/<entity_id>
    """
    entity_id = path_match.group('entity_id')

    if handler.server.hass.states.remove(entity_id):
        handler.write_json_message(
            "Entity not found", HTTP_NOT_FOUND)
    else:
        handler.write_json_message(
            "Entity removed", HTTP_OK)


def _handle_get_api_events(handler, path_match, data):
    """Handle getting overview of event listeners."""
    handler.write_json(events_json(handler.server.hass))


def _handle_api_post_events_event(handler, path_match, event_data):
    """Handle firing of an event.

    This handles the following paths: /api/events/<event_type>

    Events from /api are threated as remote events.
    """
    event_type = path_match.group('event_type')

    if event_data is not None and not isinstance(event_data, dict):
        handler.write_json_message(
            "event_data should be an object", HTTP_UNPROCESSABLE_ENTITY)
        return

    event_origin = ha.EventOrigin.remote

    # Special case handling for event STATE_CHANGED
    # We will try to convert state dicts back to State objects
    if event_type == ha.EVENT_STATE_CHANGED and event_data:
        for key in ('old_state', 'new_state'):
            state = ha.State.from_dict(event_data.get(key))

            if state:
                event_data[key] = state

    handler.server.hass.bus.fire(event_type, event_data, event_origin)

    handler.write_json_message("Event {} fired.".format(event_type))


def _handle_get_api_services(handler, path_match, data):
    """Handle getting overview of services."""
    handler.write_json(services_json(handler.server.hass))


# pylint: disable=invalid-name
def _handle_post_api_services_domain_service(handler, path_match, data):
    """Handle calling a service.

    This handles the following paths: /api/services/<domain>/<service>
    """
    domain = path_match.group('domain')
    service = path_match.group('service')

    with TrackStates(handler.server.hass) as changed_states:
        handler.server.hass.services.call(domain, service, data, True)

    handler.write_json(changed_states)


# pylint: disable=invalid-name
def _handle_post_api_event_forward(handler, path_match, data):
    """Handle adding an event forwarding target."""
    try:
        host = data['host']
        api_password = data['api_password']
    except KeyError:
        handler.write_json_message(
            "No host or api_password received.", HTTP_BAD_REQUEST)
        return

    try:
        port = int(data['port']) if 'port' in data else None
    except ValueError:
        handler.write_json_message(
            "Invalid value received for port", HTTP_UNPROCESSABLE_ENTITY)
        return

    api = rem.API(host, api_password, port)

    if not api.validate_api():
        handler.write_json_message(
            "Unable to validate API", HTTP_UNPROCESSABLE_ENTITY)
        return

    if handler.server.event_forwarder is None:
        handler.server.event_forwarder = \
            rem.EventForwarder(handler.server.hass)

    handler.server.event_forwarder.connect(api)

    handler.write_json_message("Event forwarding setup.")


def _handle_delete_api_event_forward(handler, path_match, data):
    """Handle deleting an event forwarding target."""
    try:
        host = data['host']
    except KeyError:
        handler.write_json_message("No host received.", HTTP_BAD_REQUEST)
        return

    try:
        port = int(data['port']) if 'port' in data else None
    except ValueError:
        handler.write_json_message(
            "Invalid value received for port", HTTP_UNPROCESSABLE_ENTITY)
        return

    if handler.server.event_forwarder is not None:
        api = rem.API(host, None, port)

        handler.server.event_forwarder.disconnect(api)

    handler.write_json_message("Event forwarding cancelled.")


def _handle_get_api_components(handler, path_match, data):
    """Return all the loaded components."""
    handler.write_json(handler.server.hass.config.components)


def _handle_get_api_error_log(handler, path_match, data):
    """Return the logged errors for this session."""
    handler.write_file(handler.server.hass.config.path(ERROR_LOG_FILENAME),
                       False)


def _handle_post_api_log_out(handler, path_match, data):
    """Log user out."""
    handler.send_response(HTTP_OK)
    handler.destroy_session()
    handler.end_headers()


def _handle_post_api_template(handler, path_match, data):
    """Log user out."""
    template_string = data.get('template', '')

    try:
        rendered = template.render(handler.server.hass, template_string)

        handler.send_response(HTTP_OK)
        handler.send_header(HTTP_HEADER_CONTENT_TYPE, CONTENT_TYPE_TEXT_PLAIN)
        handler.end_headers()
        handler.wfile.write(rendered.encode('utf-8'))
    except TemplateError as e:
        handler.write_json_message(str(e), HTTP_UNPROCESSABLE_ENTITY)
        return


def services_json(hass):
    """Generate services data to JSONify."""
    return [{"domain": key, "services": value}
            for key, value in hass.services.services.items()]


def events_json(hass):
    """Generate event data to JSONify."""
    return [{"event": key, "listener_count": value}
            for key, value in hass.bus.listeners.items()]
