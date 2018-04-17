"""
Support for an interface to work with a remote instance of Home Assistant.

If a connection error occurs while communicating with the API a
HomeAssistantError will be raised.

For more details about the Python API, please refer to the documentation at
https://home-assistant.io/developers/python_api/
"""
from datetime import datetime
import enum
import json
import logging
import urllib.parse

from typing import Optional

from aiohttp.hdrs import METH_GET, METH_POST, METH_DELETE, CONTENT_TYPE
import requests

from homeassistant import core as ha
from homeassistant.const import (
    URL_API, SERVER_PORT, URL_API_CONFIG, URL_API_EVENTS, URL_API_STATES,
    URL_API_SERVICES, CONTENT_TYPE_JSON, HTTP_HEADER_HA_AUTH,
    URL_API_EVENTS_EVENT, URL_API_STATES_ENTITY, URL_API_SERVICES_SERVICE)
from homeassistant.exceptions import HomeAssistantError

_LOGGER = logging.getLogger(__name__)


class APIStatus(enum.Enum):
    """Representation of an API status."""

    # pylint: disable=no-init, invalid-name
    OK = "ok"
    INVALID_PASSWORD = "invalid_password"
    CANNOT_CONNECT = "cannot_connect"
    UNKNOWN = "unknown"

    def __str__(self) -> str:
        """Return the state."""
        return self.value


class API(object):
    """Object to pass around Home Assistant API location and credentials."""

    def __init__(self, host: str, api_password: Optional[str] = None,
                 port: Optional[int] = SERVER_PORT,
                 use_ssl: bool = False) -> None:
        """Init the API."""
        self.host = host
        self.port = port
        self.api_password = api_password

        if host.startswith(("http://", "https://")):
            self.base_url = host
        elif use_ssl:
            self.base_url = "https://{}".format(host)
        else:
            self.base_url = "http://{}".format(host)

        if port is not None:
            self.base_url += ':{}'.format(port)

        self.status = None
        self._headers = {CONTENT_TYPE: CONTENT_TYPE_JSON}

        if api_password is not None:
            self._headers[HTTP_HEADER_HA_AUTH] = api_password

    def validate_api(self, force_validate: bool = False) -> bool:
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
            if method == METH_GET:
                return requests.get(
                    url, params=data, timeout=timeout, headers=self._headers)

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
        return "<API({}, password: {})>".format(
            self.base_url, 'yes' if self.api_password is not None else 'no')


class JSONEncoder(json.JSONEncoder):
    """JSONEncoder that supports Home Assistant objects."""

    # pylint: disable=method-hidden
    def default(self, o):
        """Convert Home Assistant objects.

        Hand other objects to the original method.
        """
        if isinstance(o, datetime):
            return o.isoformat()
        elif isinstance(o, set):
            return list(o)
        elif hasattr(o, 'as_dict'):
            return o.as_dict()

        return json.JSONEncoder.default(self, o)


def validate_api(api):
    """Make a call to validate API."""
    try:
        req = api(METH_GET, URL_API)

        if req.status_code == 200:
            return APIStatus.OK

        elif req.status_code == 401:
            return APIStatus.INVALID_PASSWORD

        return APIStatus.UNKNOWN

    except HomeAssistantError:
        return APIStatus.CANNOT_CONNECT


def get_event_listeners(api):
    """List of events that is being listened for."""
    try:
        req = api(METH_GET, URL_API_EVENTS)

        return req.json() if req.status_code == 200 else {}

    except (HomeAssistantError, ValueError):
        # ValueError if req.json() can't parse the json
        _LOGGER.exception("Unexpected result retrieving event listeners")

        return {}


def fire_event(api, event_type, data=None):
    """Fire an event at remote API."""
    try:
        req = api(METH_POST, URL_API_EVENTS_EVENT.format(event_type), data)

        if req.status_code != 200:
            _LOGGER.error("Error firing event: %d - %s",
                          req.status_code, req.text)

    except HomeAssistantError:
        _LOGGER.exception("Error firing event")


def get_state(api, entity_id):
    """Query given API for state of entity_id."""
    try:
        req = api(METH_GET, URL_API_STATES_ENTITY.format(entity_id))

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
        req = api(METH_GET,
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
        req = api(METH_DELETE, URL_API_STATES_ENTITY.format(entity_id))

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
        req = api(METH_POST, URL_API_STATES_ENTITY.format(entity_id), data)

        if req.status_code not in (200, 201):
            _LOGGER.error("Error changing state: %d - %s",
                          req.status_code, req.text)
            return False

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
        req = api(METH_GET, URL_API_SERVICES)

        return req.json() if req.status_code == 200 else {}

    except (HomeAssistantError, ValueError):
        # ValueError if req.json() can't parse the json
        _LOGGER.exception("Got unexpected services result")

        return {}


def call_service(api, domain, service, service_data=None, timeout=5):
    """Call a service at the remote API."""
    try:
        req = api(METH_POST,
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
        req = api(METH_GET, URL_API_CONFIG)

        if req.status_code != 200:
            return {}

        result = req.json()
        if 'components' in result:
            result['components'] = set(result['components'])
        return result

    except (HomeAssistantError, ValueError):
        # ValueError if req.json() can't parse the JSON
        _LOGGER.exception("Got unexpected configuration results")

        return {}
