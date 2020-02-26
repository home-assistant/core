"""Alexa models."""
import logging
from uuid import uuid4

from .const import (
    API_CONTEXT,
    API_DIRECTIVE,
    API_ENDPOINT,
    API_EVENT,
    API_HEADER,
    API_PAYLOAD,
    API_SCOPE,
)
from .entities import ENTITY_ADAPTERS
from .errors import AlexaInvalidEndpointError

_LOGGER = logging.getLogger(__name__)


class AlexaDirective:
    """An incoming Alexa directive."""

    def __init__(self, request):
        """Initialize a directive."""
        self._directive = request[API_DIRECTIVE]
        self.namespace = self._directive[API_HEADER]["namespace"]
        self.name = self._directive[API_HEADER]["name"]
        self.payload = self._directive[API_PAYLOAD]
        self.has_endpoint = API_ENDPOINT in self._directive

        self.entity = self.entity_id = self.endpoint = self.instance = None

    def load_entity(self, hass, config):
        """Set attributes related to the entity for this request.

        Sets these attributes when self.has_endpoint is True:

        - entity
        - entity_id
        - endpoint
        - instance (when header includes instance property)

        Behavior when self.has_endpoint is False is undefined.

        Will raise AlexaInvalidEndpointError if the endpoint in the request is
        malformed or nonexistent.
        """
        _endpoint_id = self._directive[API_ENDPOINT]["endpointId"]
        self.entity_id = _endpoint_id.replace("#", ".")

        self.entity = hass.states.get(self.entity_id)
        if not self.entity or not config.should_expose(self.entity_id):
            raise AlexaInvalidEndpointError(_endpoint_id)

        self.endpoint = ENTITY_ADAPTERS[self.entity.domain](hass, config, self.entity)
        if "instance" in self._directive[API_HEADER]:
            self.instance = self._directive[API_HEADER]["instance"]

    def response(self, name="Response", namespace="Alexa", payload=None):
        """Create an API formatted response.

        Async friendly.
        """
        response = AlexaResponse(name, namespace, payload)

        token = self._directive[API_HEADER].get("correlationToken")
        if token:
            response.set_correlation_token(token)

        if self.has_endpoint:
            response.set_endpoint(self._directive[API_ENDPOINT].copy())

        return response

    def error(
        self,
        namespace="Alexa",
        error_type="INTERNAL_ERROR",
        error_message="",
        payload=None,
    ):
        """Create a API formatted error response.

        Async friendly.
        """
        payload = payload or {}
        payload["type"] = error_type
        payload["message"] = error_message

        _LOGGER.info(
            "Request %s/%s error %s: %s",
            self._directive[API_HEADER]["namespace"],
            self._directive[API_HEADER]["name"],
            error_type,
            error_message,
        )

        return self.response(name="ErrorResponse", namespace=namespace, payload=payload)


class AlexaResponse:
    """Class to hold a response."""

    def __init__(self, name, namespace, payload=None):
        """Initialize the response."""
        payload = payload or {}
        self._response = {
            API_EVENT: {
                API_HEADER: {
                    "namespace": namespace,
                    "name": name,
                    "messageId": str(uuid4()),
                    "payloadVersion": "3",
                },
                API_PAYLOAD: payload,
            }
        }

    @property
    def name(self):
        """Return the name of this response."""
        return self._response[API_EVENT][API_HEADER]["name"]

    @property
    def namespace(self):
        """Return the namespace of this response."""
        return self._response[API_EVENT][API_HEADER]["namespace"]

    def set_correlation_token(self, token):
        """Set the correlationToken.

        This should normally mirror the value from a request, and is set by
        AlexaDirective.response() usually.
        """
        self._response[API_EVENT][API_HEADER]["correlationToken"] = token

    def set_endpoint_full(self, bearer_token, endpoint_id, cookie=None):
        """Set the endpoint dictionary.

        This is used to send proactive messages to Alexa.
        """
        self._response[API_EVENT][API_ENDPOINT] = {
            API_SCOPE: {"type": "BearerToken", "token": bearer_token}
        }

        if endpoint_id is not None:
            self._response[API_EVENT][API_ENDPOINT]["endpointId"] = endpoint_id

        if cookie is not None:
            self._response[API_EVENT][API_ENDPOINT]["cookie"] = cookie

    def set_endpoint(self, endpoint):
        """Set the endpoint.

        This should normally mirror the value from a request, and is set by
        AlexaDirective.response() usually.
        """
        self._response[API_EVENT][API_ENDPOINT] = endpoint

    def _properties(self):
        context = self._response.setdefault(API_CONTEXT, {})
        return context.setdefault("properties", [])

    def add_context_property(self, prop):
        """Add a property to the response context.

        The Alexa response includes a list of properties which provides
        feedback on how states have changed. For example if a user asks,
        "Alexa, set thermostat to 20 degrees", the API expects a response with
        the new value of the property, and Alexa will respond to the user
        "Thermostat set to 20 degrees".

        async_handle_message() will call .merge_context_properties() for every
        request automatically, however often handlers will call services to
        change state but the effects of those changes are applied
        asynchronously. Thus, handlers should call this method to confirm
        changes before returning.
        """
        self._properties().append(prop)

    def merge_context_properties(self, endpoint):
        """Add all properties from given endpoint if not already set.

        Handlers should be using .add_context_property().
        """
        properties = self._properties()
        already_set = {(p["namespace"], p["name"]) for p in properties}

        for prop in endpoint.serialize_properties():
            if (prop["namespace"], prop["name"]) not in already_set:
                self.add_context_property(prop)

    def serialize(self):
        """Return response as a JSON-able data structure."""
        return self._response
