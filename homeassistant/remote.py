"""
Support for an interface to work with a remote instance of Home Assistant.

If a connection error occurs while communicating with the API a
HomeAssistantError will be raised.

For more details about the Python API, please refer to the documentation at
https://home-assistant.io/developers/python_api/
"""
import asyncio
from datetime import datetime
import enum
import json
import logging
import time
import threading
import urllib.parse

from typing import Optional

import requests

import homeassistant.bootstrap as bootstrap
import homeassistant.core as ha
from homeassistant.const import (
    HTTP_HEADER_HA_AUTH, SERVER_PORT, URL_API, URL_API_EVENT_FORWARD,
    URL_API_EVENTS, URL_API_EVENTS_EVENT, URL_API_SERVICES, URL_API_CONFIG,
    URL_API_SERVICES_SERVICE, URL_API_STATES, URL_API_STATES_ENTITY,
    HTTP_HEADER_CONTENT_TYPE, CONTENT_TYPE_JSON)
from homeassistant.exceptions import HomeAssistantError

METHOD_GET = "get"
METHOD_POST = "post"
METHOD_DELETE = "delete"

_LOGGER = logging.getLogger(__name__)


class APIStatus(enum.Enum):
    """Represent API status."""

    # pylint: disable=no-init,invalid-name,too-few-public-methods
    OK = "ok"
    INVALID_PASSWORD = "invalid_password"
    CANNOT_CONNECT = "cannot_connect"
    UNKNOWN = "unknown"

    def __str__(self) -> str:
        """Return the state."""
        return self.value


class API(object):
    """Object to pass around Home Assistant API location and credentials."""

    # pylint: disable=too-few-public-methods
    def __init__(self, host: str, api_password: Optional[str]=None,
                 port: Optional[int]=None, use_ssl: bool=False) -> None:
        """Initalize the API."""
        self.host = host
        self.port = port or SERVER_PORT
        self.api_password = api_password
        if use_ssl:
            self.base_url = "https://{}:{}".format(host, self.port)
        else:
            self.base_url = "http://{}:{}".format(host, self.port)
        self.status = None
        self._headers = {
            HTTP_HEADER_CONTENT_TYPE: CONTENT_TYPE_JSON,
        }

        if api_password is not None:
            self._headers[HTTP_HEADER_HA_AUTH] = api_password

    def validate_api(self, force_validate: bool=False) -> bool:
        """Test if we can communicate with the API."""
        if self.status is None or force_validate:
            self.status = validate_api(self)

        return self.status == APIStatus.OK

    def __call__(self, method, path, data=None, timeout=5):
        """Make a call to the Home Assistant API."""
        if data is not None:
            data = json.dumps(data, cls=JSONEncoder)

        url = urllib.parse.urljoin(self.base_url, path)

        try:
            if method == METHOD_GET:
                return requests.get(
                    url, params=data, timeout=timeout, headers=self._headers)
            else:
                return requests.request(
                    method, url, data=data, timeout=timeout,
                    headers=self._headers)

        except requests.exceptions.ConnectionError:
            _LOGGER.exception("Error connecting to server")
            raise HomeAssistantError("Error connecting to server")

        except requests.exceptions.Timeout:
            error = "Timeout when talking to {}".format(self.host)
            _LOGGER.exception(error)
            raise HomeAssistantError(error)

    def __repr__(self) -> str:
        """Return the representation of the API."""
        return "API({}, {}, {})".format(
            self.host, self.api_password, self.port)


class HomeAssistant(ha.HomeAssistant):
    """Home Assistant that forwards work."""

    # pylint: disable=super-init-not-called,too-many-instance-attributes
    def __init__(self, remote_api, local_api=None, loop=None):
        """Initalize the forward instance."""
        if not remote_api.validate_api():
            raise HomeAssistantError(
                "Remote API at {}:{} not valid: {}".format(
                    remote_api.host, remote_api.port, remote_api.status))

        self.remote_api = remote_api

        self.loop = loop or asyncio.get_event_loop()
        self.pool = pool = ha.create_worker_pool()

        self.bus = EventBus(remote_api, pool, self.loop)
        self.services = ha.ServiceRegistry(self.bus, self.add_job, self.loop)
        self.states = StateMachine(self.bus, self.loop, self.remote_api)
        self.config = ha.Config()
        self.state = ha.CoreState.not_running

        self.config.api = local_api

    def start(self):
        """Start the instance."""
        # Ensure a local API exists to connect with remote
        if 'api' not in self.config.components:
            if not bootstrap.setup_component(self, 'api'):
                raise HomeAssistantError(
                    'Unable to setup local API to receive events')

        self.state = ha.CoreState.starting
        ha.async_create_timer(self)

        self.bus.fire(ha.EVENT_HOMEASSISTANT_START,
                      origin=ha.EventOrigin.remote)

        # Ensure local HTTP is started
        self.block_till_done()
        self.state = ha.CoreState.running
        time.sleep(0.05)

        # Setup that events from remote_api get forwarded to local_api
        # Do this after we are running, otherwise HTTP is not started
        # or requests are blocked
        if not connect_remote_events(self.remote_api, self.config.api):
            raise HomeAssistantError((
                'Could not setup event forwarding from api {} to '
                'local api {}').format(self.remote_api, self.config.api))

    def stop(self):
        """Stop Home Assistant and shuts down all threads."""
        _LOGGER.info("Stopping")
        self.state = ha.CoreState.stopping

        self.bus.fire(ha.EVENT_HOMEASSISTANT_STOP,
                      origin=ha.EventOrigin.remote)

        self.pool.stop()

        # Disconnect master event forwarding
        disconnect_remote_events(self.remote_api, self.config.api)
        self.state = ha.CoreState.not_running


class EventBus(ha.EventBus):
    """EventBus implementation that forwards fire_event to remote API."""

    # pylint: disable=too-few-public-methods
    def __init__(self, api, pool, loop):
        """Initalize the eventbus."""
        super().__init__(pool, loop)
        self._api = api

    def fire(self, event_type, event_data=None, origin=ha.EventOrigin.local):
        """Forward local events to remote target.

        Handles remote event as usual.
        """
        # All local events that are not TIME_CHANGED are forwarded to API
        if origin == ha.EventOrigin.local and \
           event_type != ha.EVENT_TIME_CHANGED:

            fire_event(self._api, event_type, event_data)

        else:
            super().fire(event_type, event_data, origin)


class EventForwarder(object):
    """Listens for events and forwards to specified APIs."""

    def __init__(self, hass, restrict_origin=None):
        """Initalize the event forwarder."""
        self.hass = hass
        self.restrict_origin = restrict_origin

        # We use a tuple (host, port) as key to ensure
        # that we do not forward to the same host twice
        self._targets = {}

        self._lock = threading.Lock()
        self._unsub_listener = None

    def connect(self, api):
        """Attach to a Home Assistant instance and forward events.

        Will overwrite old target if one exists with same host/port.
        """
        with self._lock:
            if self._unsub_listener is None:
                self._unsub_listener = self.hass.bus.listen(
                    ha.MATCH_ALL, self._event_listener)

            key = (api.host, api.port)

            self._targets[key] = api

    def disconnect(self, api):
        """Remove target from being forwarded to."""
        with self._lock:
            key = (api.host, api.port)

            did_remove = self._targets.pop(key, None) is None

            if len(self._targets) == 0:
                # Remove event listener if no forwarding targets present
                self._unsub_listener()
                self._unsub_listener = None

            return did_remove

    def _event_listener(self, event):
        """Listen and forward all events."""
        with self._lock:
            # We don't forward time events or, if enabled, non-local events
            if event.event_type == ha.EVENT_TIME_CHANGED or \
               (self.restrict_origin and event.origin != self.restrict_origin):
                return

            for api in self._targets.values():
                fire_event(api, event.event_type, event.data)


class StateMachine(ha.StateMachine):
    """Fire set events to an API. Uses state_change events to track states."""

    def __init__(self, bus, loop, api):
        """Initalize the statemachine."""
        super().__init__(bus, loop)
        self._api = api
        self.mirror()

        bus.listen(ha.EVENT_STATE_CHANGED, self._state_changed_listener)

    def remove(self, entity_id):
        """Remove the state of an entity.

        Returns boolean to indicate if an entity was removed.
        """
        return remove_state(self._api, entity_id)

    def set(self, entity_id, new_state, attributes=None, force_update=False):
        """Call set_state on remote API."""
        set_state(self._api, entity_id, new_state, attributes, force_update)

    def mirror(self):
        """Discard current data and mirrors the remote state machine."""
        self._states = {state.entity_id: state for state
                        in get_states(self._api)}

    def _state_changed_listener(self, event):
        """Listen for state changed events and applies them."""
        if event.data['new_state'] is None:
            self._states.pop(event.data['entity_id'], None)
        else:
            self._states[event.data['entity_id']] = event.data['new_state']


class JSONEncoder(json.JSONEncoder):
    """JSONEncoder that supports Home Assistant objects."""

    # pylint: disable=too-few-public-methods,method-hidden
    def default(self, obj):
        """Convert Home Assistant objects.

        Hand other objects to the original method.
        """
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif hasattr(obj, 'as_dict'):
            return obj.as_dict()

        try:
            return json.JSONEncoder.default(self, obj)
        except TypeError:
            # If the JSON serializer couldn't serialize it
            # it might be a generator, convert it to a list
            try:
                return [self.default(child_obj)
                        for child_obj in obj]
            except TypeError:
                # Ok, we're lost, cause the original error
                return json.JSONEncoder.default(self, obj)


def validate_api(api):
    """Make a call to validate API."""
    try:
        req = api(METHOD_GET, URL_API)

        if req.status_code == 200:
            return APIStatus.OK

        elif req.status_code == 401:
            return APIStatus.INVALID_PASSWORD

        else:
            return APIStatus.UNKNOWN

    except HomeAssistantError:
        return APIStatus.CANNOT_CONNECT


def connect_remote_events(from_api, to_api):
    """Setup from_api to forward all events to to_api."""
    data = {
        'host': to_api.host,
        'api_password': to_api.api_password,
        'port': to_api.port
    }

    try:
        req = from_api(METHOD_POST, URL_API_EVENT_FORWARD, data)

        if req.status_code == 200:
            return True
        else:
            _LOGGER.error(
                "Error setting up event forwarding: %s - %s",
                req.status_code, req.text)

            return False

    except HomeAssistantError:
        _LOGGER.exception("Error setting up event forwarding")
        return False


def disconnect_remote_events(from_api, to_api):
    """Disconnect forwarding events from from_api to to_api."""
    data = {
        'host': to_api.host,
        'port': to_api.port
    }

    try:
        req = from_api(METHOD_DELETE, URL_API_EVENT_FORWARD, data)

        if req.status_code == 200:
            return True
        else:
            _LOGGER.error(
                "Error removing event forwarding: %s - %s",
                req.status_code, req.text)

            return False

    except HomeAssistantError:
        _LOGGER.exception("Error removing an event forwarder")
        return False


def get_event_listeners(api):
    """List of events that is being listened for."""
    try:
        req = api(METHOD_GET, URL_API_EVENTS)

        return req.json() if req.status_code == 200 else {}

    except (HomeAssistantError, ValueError):
        # ValueError if req.json() can't parse the json
        _LOGGER.exception("Unexpected result retrieving event listeners")

        return {}


def fire_event(api, event_type, data=None):
    """Fire an event at remote API."""
    try:
        req = api(METHOD_POST, URL_API_EVENTS_EVENT.format(event_type), data)

        if req.status_code != 200:
            _LOGGER.error("Error firing event: %d - %s",
                          req.status_code, req.text)

    except HomeAssistantError:
        _LOGGER.exception("Error firing event")


def get_state(api, entity_id):
    """Query given API for state of entity_id."""
    try:
        req = api(METHOD_GET, URL_API_STATES_ENTITY.format(entity_id))

        # req.status_code == 422 if entity does not exist

        return ha.State.from_dict(req.json()) \
            if req.status_code == 200 else None

    except (HomeAssistantError, ValueError):
        # ValueError if req.json() can't parse the json
        _LOGGER.exception("Error fetching state")

        return None


def get_states(api):
    """Query given API for all states."""
    try:
        req = api(METHOD_GET,
                  URL_API_STATES)

        return [ha.State.from_dict(item) for
                item in req.json()]

    except (HomeAssistantError, ValueError, AttributeError):
        # ValueError if req.json() can't parse the json
        _LOGGER.exception("Error fetching states")

        return []


def remove_state(api, entity_id):
    """Call API to remove state for entity_id.

    Return True if entity is gone (removed/never existed).
    """
    try:
        req = api(METHOD_DELETE, URL_API_STATES_ENTITY.format(entity_id))

        if req.status_code in (200, 404):
            return True

        _LOGGER.error("Error removing state: %d - %s",
                      req.status_code, req.text)
        return False
    except HomeAssistantError:
        _LOGGER.exception("Error removing state")

        return False


def set_state(api, entity_id, new_state, attributes=None, force_update=False):
    """Tell API to update state for entity_id.

    Return True if success.
    """
    attributes = attributes or {}

    data = {'state': new_state,
            'attributes': attributes,
            'force_update': force_update}

    try:
        req = api(METHOD_POST,
                  URL_API_STATES_ENTITY.format(entity_id),
                  data)

        if req.status_code not in (200, 201):
            _LOGGER.error("Error changing state: %d - %s",
                          req.status_code, req.text)
            return False
        else:
            return True

    except HomeAssistantError:
        _LOGGER.exception("Error setting state")

        return False


def is_state(api, entity_id, state):
    """Query API to see if entity_id is specified state."""
    cur_state = get_state(api, entity_id)

    return cur_state and cur_state.state == state


def get_services(api):
    """Return a list of dicts.

    Each dict has a string "domain" and a list of strings "services".
    """
    try:
        req = api(METHOD_GET, URL_API_SERVICES)

        return req.json() if req.status_code == 200 else {}

    except (HomeAssistantError, ValueError):
        # ValueError if req.json() can't parse the json
        _LOGGER.exception("Got unexpected services result")

        return {}


def call_service(api, domain, service, service_data=None, timeout=5):
    """Call a service at the remote API."""
    try:
        req = api(METHOD_POST,
                  URL_API_SERVICES_SERVICE.format(domain, service),
                  service_data, timeout=timeout)

        if req.status_code != 200:
            _LOGGER.error("Error calling service: %d - %s",
                          req.status_code, req.text)

    except HomeAssistantError:
        _LOGGER.exception("Error calling service")


def get_config(api):
    """Return configuration."""
    try:
        req = api(METHOD_GET, URL_API_CONFIG)

        return req.json() if req.status_code == 200 else {}

    except (HomeAssistantError, ValueError):
        # ValueError if req.json() can't parse the JSON
        _LOGGER.exception("Got unexpected configuration results")

        return {}
