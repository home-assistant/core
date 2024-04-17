"""Alexa state report code."""

from __future__ import annotations

from asyncio import timeout
from http import HTTPStatus
import json
import logging
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, cast
from uuid import uuid4

import aiohttp

from homeassistant.components import event
from homeassistant.const import EVENT_STATE_CHANGED, STATE_ON
from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    EventStateChangedData,
    HomeAssistant,
    State,
    callback,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.significant_change import create_checker
import homeassistant.util.dt as dt_util
from homeassistant.util.json import JsonObjectType, json_loads_object

from .const import (
    API_CHANGE,
    API_CONTEXT,
    API_DIRECTIVE,
    API_ENDPOINT,
    API_EVENT,
    API_HEADER,
    API_PAYLOAD,
    API_SCOPE,
    DATE_FORMAT,
    DOMAIN,
    Cause,
)
from .diagnostics import async_redact_auth_data
from .entities import ENTITY_ADAPTERS, AlexaEntity
from .errors import AlexaInvalidEndpointError, NoTokenAvailable, RequireRelink

if TYPE_CHECKING:
    from .config import AbstractConfig

_LOGGER = logging.getLogger(__name__)
DEFAULT_TIMEOUT = 10

TO_REDACT = {"correlationToken", "token"}


class AlexaDirective:
    """An incoming Alexa directive."""

    entity: State
    entity_id: str | None
    endpoint: AlexaEntity
    instance: str | None

    def __init__(self, request: dict[str, Any]) -> None:
        """Initialize a directive."""
        self._directive: dict[str, Any] = request[API_DIRECTIVE]
        self.namespace: str = self._directive[API_HEADER]["namespace"]
        self.name: str = self._directive[API_HEADER]["name"]
        self.payload: dict[str, Any] = self._directive[API_PAYLOAD]
        self.has_endpoint: bool = API_ENDPOINT in self._directive
        self.instance = None
        self.entity_id = None

    def load_entity(self, hass: HomeAssistant, config: AbstractConfig) -> None:
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
        _endpoint_id: str = self._directive[API_ENDPOINT]["endpointId"]
        self.entity_id = _endpoint_id.replace("#", ".")

        entity: State | None = hass.states.get(self.entity_id)
        if not entity or not config.should_expose(self.entity_id):
            raise AlexaInvalidEndpointError(_endpoint_id)
        self.entity = entity

        self.endpoint = ENTITY_ADAPTERS[self.entity.domain](hass, config, self.entity)
        if "instance" in self._directive[API_HEADER]:
            self.instance = self._directive[API_HEADER]["instance"]

    def response(
        self,
        name: str = "Response",
        namespace: str = "Alexa",
        payload: dict[str, Any] | None = None,
    ) -> AlexaResponse:
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
        namespace: str = "Alexa",
        error_type: str = "INTERNAL_ERROR",
        error_message: str = "",
        payload: dict[str, Any] | None = None,
    ) -> AlexaResponse:
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

    def __init__(
        self, name: str, namespace: str, payload: dict[str, Any] | None = None
    ) -> None:
        """Initialize the response."""
        payload = payload or {}
        self._response: dict[str, Any] = {
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
    def name(self) -> str:
        """Return the name of this response."""
        name: str = self._response[API_EVENT][API_HEADER]["name"]
        return name

    @property
    def namespace(self) -> str:
        """Return the namespace of this response."""
        namespace: str = self._response[API_EVENT][API_HEADER]["namespace"]
        return namespace

    def set_correlation_token(self, token: str) -> None:
        """Set the correlationToken.

        This should normally mirror the value from a request, and is set by
        AlexaDirective.response() usually.
        """
        self._response[API_EVENT][API_HEADER]["correlationToken"] = token

    def set_endpoint_full(
        self, bearer_token: str | None, endpoint_id: str | None
    ) -> None:
        """Set the endpoint dictionary.

        This is used to send proactive messages to Alexa.
        """
        self._response[API_EVENT][API_ENDPOINT] = {
            API_SCOPE: {"type": "BearerToken", "token": bearer_token}
        }

        if endpoint_id is not None:
            self._response[API_EVENT][API_ENDPOINT]["endpointId"] = endpoint_id

    def set_endpoint(self, endpoint: dict[str, Any]) -> None:
        """Set the endpoint.

        This should normally mirror the value from a request, and is set by
        AlexaDirective.response() usually.
        """
        self._response[API_EVENT][API_ENDPOINT] = endpoint

    def _properties(self) -> list[dict[str, Any]]:
        context: dict[str, Any] = self._response.setdefault(API_CONTEXT, {})
        properties: list[dict[str, Any]] = context.setdefault("properties", [])
        return properties

    def add_context_property(self, prop: dict[str, Any]) -> None:
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

    def merge_context_properties(self, endpoint: AlexaEntity) -> None:
        """Add all properties from given endpoint if not already set.

        Handlers should be using .add_context_property().
        """
        properties = self._properties()
        already_set = {(p["namespace"], p["name"]) for p in properties}

        for prop in endpoint.serialize_properties():
            if (prop["namespace"], prop["name"]) not in already_set:
                self.add_context_property(prop)

    def serialize(self) -> dict[str, Any]:
        """Return response as a JSON-able data structure."""
        return self._response


async def async_enable_proactive_mode(
    hass: HomeAssistant, smart_home_config: AbstractConfig
) -> CALLBACK_TYPE | None:
    """Enable the proactive mode.

    Proactive mode makes this component report state changes to Alexa.
    """
    # Validate we can get access token.
    await smart_home_config.async_get_access_token()

    @callback
    def extra_significant_check(
        hass: HomeAssistant,
        old_state: str,
        old_attrs: dict[Any, Any] | MappingProxyType[Any, Any],
        old_extra_arg: Any,
        new_state: str,
        new_attrs: dict[str, Any] | MappingProxyType[Any, Any],
        new_extra_arg: Any,
    ) -> bool:
        """Check if the serialized data has changed."""
        return old_extra_arg is not None and old_extra_arg != new_extra_arg

    checker = await create_checker(hass, DOMAIN, extra_significant_check)

    @callback
    def _async_entity_state_filter(data: EventStateChangedData) -> bool:
        if not hass.is_running:
            return False

        if not (new_state := data["new_state"]):
            return False

        if new_state.domain not in ENTITY_ADAPTERS:
            return False

        changed_entity = data["entity_id"]
        if not smart_home_config.should_expose(changed_entity):
            _LOGGER.debug("Not exposing %s because filtered by config", changed_entity)
            return False

        return True

    async def _async_entity_state_listener(
        event_: Event[EventStateChangedData],
    ) -> None:
        data = event_.data
        new_state = data["new_state"]
        if TYPE_CHECKING:
            assert new_state is not None

        alexa_changed_entity: AlexaEntity = ENTITY_ADAPTERS[new_state.domain](
            hass, smart_home_config, new_state
        )
        # Determine how entity should be reported on
        should_report = False
        should_doorbell = False

        for interface in alexa_changed_entity.interfaces():
            if not should_report and interface.properties_proactively_reported():
                should_report = True

            if interface.name() == "Alexa.DoorbellEventSource":
                should_doorbell = True
                break

        if not should_report and not should_doorbell:
            return

        if should_doorbell:
            old_state = data["old_state"]
            if (
                new_state.domain == event.DOMAIN
                or new_state.state == STATE_ON
                and (old_state is None or old_state.state != STATE_ON)
            ):
                await async_send_doorbell_event_message(
                    hass, smart_home_config, alexa_changed_entity
                )
            return

        alexa_properties = list(alexa_changed_entity.serialize_properties())

        if not checker.async_is_significant_change(
            new_state, extra_arg=alexa_properties
        ):
            return

        await async_send_changereport_message(
            hass, smart_home_config, alexa_changed_entity, alexa_properties
        )

    return hass.bus.async_listen(
        EVENT_STATE_CHANGED,
        _async_entity_state_listener,
        event_filter=_async_entity_state_filter,
    )


async def async_send_changereport_message(
    hass: HomeAssistant,
    config: AbstractConfig,
    alexa_entity: AlexaEntity,
    alexa_properties: list[dict[str, Any]],
    *,
    invalidate_access_token: bool = True,
) -> None:
    """Send a ChangeReport message for an Alexa entity.

    https://developer.amazon.com/docs/smarthome/state-reporting-for-a-smart-home-skill.html#report-state-with-changereport-events
    """
    try:
        token = await config.async_get_access_token()
    except (RequireRelink, NoTokenAvailable):
        await config.set_authorized(False)
        _LOGGER.error(
            "Error when sending ChangeReport to Alexa, could not get access token"
        )
        return

    headers: dict[str, Any] = {"Authorization": f"Bearer {token}"}

    endpoint = alexa_entity.alexa_id()

    payload: dict[str, Any] = {
        API_CHANGE: {
            "cause": {"type": Cause.APP_INTERACTION},
            "properties": alexa_properties,
        }
    }

    message = AlexaResponse(name="ChangeReport", namespace="Alexa", payload=payload)
    message.set_endpoint_full(token, endpoint)

    message_serialized = message.serialize()
    session = async_get_clientsession(hass)

    assert config.endpoint is not None
    try:
        async with timeout(DEFAULT_TIMEOUT):
            response = await session.post(
                config.endpoint,
                headers=headers,
                json=message_serialized,
                allow_redirects=True,
            )

    except (TimeoutError, aiohttp.ClientError):
        _LOGGER.error("Timeout sending report to Alexa for %s", alexa_entity.entity_id)
        return

    response_text = await response.text()

    if _LOGGER.isEnabledFor(logging.DEBUG):
        _LOGGER.debug(
            "Sent: %s", json.dumps(async_redact_auth_data(message_serialized))
        )
        _LOGGER.debug("Received (%s): %s", response.status, response_text)

    if response.status == HTTPStatus.ACCEPTED:
        return

    response_json = json_loads_object(response_text)
    response_payload = cast(JsonObjectType, response_json["payload"])

    if response_payload["code"] == "INVALID_ACCESS_TOKEN_EXCEPTION":
        if invalidate_access_token:
            # Invalidate the access token and try again
            config.async_invalidate_access_token()
            return await async_send_changereport_message(
                hass,
                config,
                alexa_entity,
                alexa_properties,
                invalidate_access_token=False,
            )
        await config.set_authorized(False)

    _LOGGER.error(
        "Error when sending ChangeReport for %s to Alexa: %s: %s",
        alexa_entity.entity_id,
        response_payload["code"],
        response_payload["description"],
    )


async def async_send_add_or_update_message(
    hass: HomeAssistant, config: AbstractConfig, entity_ids: list[str]
) -> aiohttp.ClientResponse:
    """Send an AddOrUpdateReport message for entities.

    https://developer.amazon.com/docs/device-apis/alexa-discovery.html#add-or-update-report
    """
    token = await config.async_get_access_token()

    headers: dict[str, Any] = {"Authorization": f"Bearer {token}"}

    endpoints: list[dict[str, Any]] = []

    for entity_id in entity_ids:
        if (domain := entity_id.split(".", 1)[0]) not in ENTITY_ADAPTERS:
            continue

        if (state := hass.states.get(entity_id)) is None:
            continue

        alexa_entity = ENTITY_ADAPTERS[domain](hass, config, state)
        endpoints.append(alexa_entity.serialize_discovery())

    payload: dict[str, Any] = {
        "endpoints": endpoints,
        "scope": {"type": "BearerToken", "token": token},
    }

    message = AlexaResponse(
        name="AddOrUpdateReport", namespace="Alexa.Discovery", payload=payload
    )

    message_serialized = message.serialize()
    session = async_get_clientsession(hass)

    assert config.endpoint is not None
    return await session.post(
        config.endpoint, headers=headers, json=message_serialized, allow_redirects=True
    )


async def async_send_delete_message(
    hass: HomeAssistant, config: AbstractConfig, entity_ids: list[str]
) -> aiohttp.ClientResponse:
    """Send an DeleteReport message for entities.

    https://developer.amazon.com/docs/device-apis/alexa-discovery.html#deletereport-event
    """
    token = await config.async_get_access_token()

    headers: dict[str, Any] = {"Authorization": f"Bearer {token}"}

    endpoints: list[dict[str, Any]] = []

    for entity_id in entity_ids:
        domain = entity_id.split(".", 1)[0]

        if domain not in ENTITY_ADAPTERS:
            continue

        endpoints.append({"endpointId": config.generate_alexa_id(entity_id)})

    payload: dict[str, Any] = {
        "endpoints": endpoints,
        "scope": {"type": "BearerToken", "token": token},
    }

    message = AlexaResponse(
        name="DeleteReport", namespace="Alexa.Discovery", payload=payload
    )

    message_serialized = message.serialize()
    session = async_get_clientsession(hass)

    assert config.endpoint is not None
    return await session.post(
        config.endpoint, headers=headers, json=message_serialized, allow_redirects=True
    )


async def async_send_doorbell_event_message(
    hass: HomeAssistant, config: AbstractConfig, alexa_entity: AlexaEntity
) -> None:
    """Send a DoorbellPress event message for an Alexa entity.

    https://developer.amazon.com/en-US/docs/alexa/device-apis/alexa-doorbelleventsource.html
    """
    token = await config.async_get_access_token()

    headers: dict[str, Any] = {"Authorization": f"Bearer {token}"}

    endpoint = alexa_entity.alexa_id()

    message = AlexaResponse(
        name="DoorbellPress",
        namespace="Alexa.DoorbellEventSource",
        payload={
            "cause": {"type": Cause.PHYSICAL_INTERACTION},
            "timestamp": dt_util.utcnow().strftime(DATE_FORMAT),
        },
    )

    message.set_endpoint_full(token, endpoint)

    message_serialized = message.serialize()
    session = async_get_clientsession(hass)

    assert config.endpoint is not None
    try:
        async with timeout(DEFAULT_TIMEOUT):
            response = await session.post(
                config.endpoint,
                headers=headers,
                json=message_serialized,
                allow_redirects=True,
            )

    except (TimeoutError, aiohttp.ClientError):
        _LOGGER.error("Timeout sending report to Alexa for %s", alexa_entity.entity_id)
        return

    response_text = await response.text()

    if _LOGGER.isEnabledFor(logging.DEBUG):
        _LOGGER.debug(
            "Sent: %s", json.dumps(async_redact_auth_data(message_serialized))
        )
        _LOGGER.debug("Received (%s): %s", response.status, response_text)

    if response.status == HTTPStatus.ACCEPTED:
        return

    response_json = json_loads_object(response_text)
    response_payload = cast(JsonObjectType, response_json["payload"])

    _LOGGER.error(
        "Error when sending DoorbellPress event for %s to Alexa: %s: %s",
        alexa_entity.entity_id,
        response_payload["code"],
        response_payload["description"],
    )
