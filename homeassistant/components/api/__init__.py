"""Rest API for Home Assistant."""

import asyncio
from asyncio import shield, timeout
from functools import lru_cache
from http import HTTPStatus
import logging
from typing import Any

from aiohttp import web
from aiohttp.web_exceptions import HTTPBadRequest
import voluptuous as vol

from homeassistant import core as ha
from homeassistant.auth.models import User
from homeassistant.auth.permissions.const import POLICY_READ
from homeassistant.components.http import (
    KEY_HASS,
    KEY_HASS_USER,
    HomeAssistantView,
    require_admin,
)
from homeassistant.const import (
    CONTENT_TYPE_JSON,
    EVENT_HOMEASSISTANT_STOP,
    EVENT_STATE_CHANGED,
    KEY_DATA_LOGGING as DATA_LOGGING,
    MATCH_ALL,
    URL_API,
    URL_API_COMPONENTS,
    URL_API_CONFIG,
    URL_API_CORE_STATE,
    URL_API_ERROR_LOG,
    URL_API_EVENTS,
    URL_API_SERVICES,
    URL_API_STATES,
    URL_API_STREAM,
    URL_API_TEMPLATE,
)
from homeassistant.core import Event, EventStateChangedData, HomeAssistant
from homeassistant.exceptions import (
    InvalidEntityFormatError,
    InvalidStateError,
    ServiceNotFound,
    TemplateError,
    Unauthorized,
)
from homeassistant.helpers import config_validation as cv, recorder, template
from homeassistant.helpers.json import json_dumps, json_fragment
from homeassistant.helpers.service import async_get_all_descriptions
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.event_type import EventType
from homeassistant.util.json import json_loads

_LOGGER = logging.getLogger(__name__)

ATTR_BASE_URL = "base_url"
ATTR_EXTERNAL_URL = "external_url"
ATTR_INTERNAL_URL = "internal_url"
ATTR_LOCATION_NAME = "location_name"
ATTR_INSTALLATION_TYPE = "installation_type"
ATTR_REQUIRES_API_PASSWORD = "requires_api_password"
ATTR_UUID = "uuid"
ATTR_VERSION = "version"

DOMAIN = "api"
STREAM_PING_PAYLOAD = "ping"
STREAM_PING_INTERVAL = 50  # seconds
SERVICE_WAIT_TIMEOUT = 10

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the API with the HTTP interface."""
    hass.http.register_view(APIStatusView)
    hass.http.register_view(APICoreStateView)
    hass.http.register_view(APIEventStream)
    hass.http.register_view(APIConfigView)
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
    name = "api:status"

    @ha.callback
    def get(self, request: web.Request) -> web.Response:
        """Retrieve if API is running."""
        return self.json_message("API running.")


class APICoreStateView(HomeAssistantView):
    """View to handle core state requests."""

    url = URL_API_CORE_STATE
    name = "api:core:state"

    @ha.callback
    def get(self, request: web.Request) -> web.Response:
        """Retrieve the current core state.

        This API is intended to be a fast and lightweight way to check if the
        Home Assistant core is running. Its primary use case is for supervisor
        to check if Home Assistant is running.
        """
        hass = request.app[KEY_HASS]
        migration = recorder.async_migration_in_progress(hass)
        live = recorder.async_migration_is_live(hass)
        recorder_state = {"migration_in_progress": migration, "migration_is_live": live}
        return self.json({"state": hass.state.value, "recorder_state": recorder_state})


class APIEventStream(HomeAssistantView):
    """View to handle EventStream requests."""

    url = URL_API_STREAM
    name = "api:stream"

    @require_admin
    async def get(self, request: web.Request) -> web.StreamResponse:
        """Provide a streaming interface for the event bus."""
        hass = request.app[KEY_HASS]
        stop_obj = object()
        to_write: asyncio.Queue[object | str] = asyncio.Queue()

        restrict: list[EventType[Any] | str] | None = None
        if restrict_str := request.query.get("restrict"):
            restrict = [*restrict_str.split(","), EVENT_HOMEASSISTANT_STOP]

        async def forward_events(event: Event) -> None:
            """Forward events to the open request."""
            if restrict and event.event_type not in restrict:
                return

            _LOGGER.debug("STREAM %s FORWARDING %s", id(stop_obj), event)

            if event.event_type == EVENT_HOMEASSISTANT_STOP:
                data = stop_obj
            else:
                data = json_dumps(event)

            await to_write.put(data)

        response = web.StreamResponse()
        response.content_type = "text/event-stream"
        await response.prepare(request)

        unsub_stream = hass.bus.async_listen(MATCH_ALL, forward_events)

        try:
            _LOGGER.debug("STREAM %s ATTACHED", id(stop_obj))

            # Fire off one message so browsers fire open event right away
            await to_write.put(STREAM_PING_PAYLOAD)

            while True:
                try:
                    async with timeout(STREAM_PING_INTERVAL):
                        payload = await to_write.get()

                    if payload is stop_obj:
                        break

                    msg = f"data: {payload}\n\n"
                    _LOGGER.debug("STREAM %s WRITING %s", id(stop_obj), msg.strip())
                    await response.write(msg.encode("UTF-8"))
                except TimeoutError:
                    await to_write.put(STREAM_PING_PAYLOAD)

        except asyncio.CancelledError:
            _LOGGER.debug("STREAM %s ABORT", id(stop_obj))

        finally:
            _LOGGER.debug("STREAM %s RESPONSE CLOSED", id(stop_obj))
            unsub_stream()

        return response


class APIConfigView(HomeAssistantView):
    """View to handle Configuration requests."""

    url = URL_API_CONFIG
    name = "api:config"

    @ha.callback
    def get(self, request: web.Request) -> web.Response:
        """Get current configuration."""
        return self.json(request.app[KEY_HASS].config.as_dict())


class APIStatesView(HomeAssistantView):
    """View to handle States requests."""

    url = URL_API_STATES
    name = "api:states"

    @ha.callback
    def get(self, request: web.Request) -> web.Response:
        """Get current states."""
        user: User = request[KEY_HASS_USER]
        hass = request.app[KEY_HASS]
        if user.is_admin:
            states = (state.as_dict_json for state in hass.states.async_all())
        else:
            entity_perm = user.permissions.check_entity
            states = (
                state.as_dict_json
                for state in hass.states.async_all()
                if entity_perm(state.entity_id, "read")
            )
        response = web.Response(
            body=b"".join((b"[", b",".join(states), b"]")),
            content_type=CONTENT_TYPE_JSON,
            zlib_executor_size=32768,
        )
        response.enable_compression()
        return response


class APIEntityStateView(HomeAssistantView):
    """View to handle EntityState requests."""

    url = "/api/states/{entity_id}"
    name = "api:entity-state"

    @ha.callback
    def get(self, request: web.Request, entity_id: str) -> web.Response:
        """Retrieve state of entity."""
        user: User = request[KEY_HASS_USER]
        hass = request.app[KEY_HASS]
        if not user.permissions.check_entity(entity_id, POLICY_READ):
            raise Unauthorized(entity_id=entity_id)

        if state := hass.states.get(entity_id):
            return web.Response(
                body=state.as_dict_json,
                content_type=CONTENT_TYPE_JSON,
            )
        return self.json_message("Entity not found.", HTTPStatus.NOT_FOUND)

    async def post(self, request: web.Request, entity_id: str) -> web.Response:
        """Update state of entity."""
        user: User = request[KEY_HASS_USER]
        if not user.is_admin:
            raise Unauthorized(entity_id=entity_id)
        hass = request.app[KEY_HASS]

        body = await request.text()

        data: Any = json_loads(body) if body else None

        if not isinstance(data, dict):
            return self.json_message(
                "State data should be a JSON object", HTTPStatus.BAD_REQUEST
            )
        if (new_state := data.get("state")) is None:
            return self.json_message(
                "No state attribute specified.", HTTPStatus.BAD_REQUEST
            )

        attributes = data.get("attributes")
        force_update = data.get("force_update", False)

        is_new_state = hass.states.get(entity_id) is None

        # Write state
        try:
            hass.states.async_set(
                entity_id, new_state, attributes, force_update, self.context(request)
            )
        except InvalidEntityFormatError:
            return self.json_message(
                "Invalid entity ID specified.", HTTPStatus.BAD_REQUEST
            )
        except InvalidStateError:
            return self.json_message("Invalid state specified.", HTTPStatus.BAD_REQUEST)

        # Read the state back for our response
        status_code = HTTPStatus.CREATED if is_new_state else HTTPStatus.OK
        state = hass.states.get(entity_id)
        assert state
        resp = self.json(state.as_dict(), status_code)

        resp.headers.add("Location", f"/api/states/{entity_id}")

        return resp

    @ha.callback
    def delete(self, request: web.Request, entity_id: str) -> web.Response:
        """Remove entity."""
        if not request[KEY_HASS_USER].is_admin:
            raise Unauthorized(entity_id=entity_id)
        if request.app[KEY_HASS].states.async_remove(entity_id):
            return self.json_message("Entity removed.")
        return self.json_message("Entity not found.", HTTPStatus.NOT_FOUND)


class APIEventListenersView(HomeAssistantView):
    """View to handle EventListeners requests."""

    url = URL_API_EVENTS
    name = "api:event-listeners"

    @ha.callback
    def get(self, request: web.Request) -> web.Response:
        """Get event listeners."""
        return self.json(async_events_json(request.app[KEY_HASS]))


class APIEventView(HomeAssistantView):
    """View to handle Event requests."""

    url = "/api/events/{event_type}"
    name = "api:event"

    @require_admin
    async def post(self, request: web.Request, event_type: str) -> web.Response:
        """Fire events."""
        body = await request.text()
        try:
            event_data: Any = json_loads(body) if body else None
        except ValueError:
            return self.json_message(
                "Event data should be valid JSON.", HTTPStatus.BAD_REQUEST
            )

        if event_data is not None and not isinstance(event_data, dict):
            return self.json_message(
                "Event data should be a JSON object", HTTPStatus.BAD_REQUEST
            )

        # Special case handling for event STATE_CHANGED
        # We will try to convert state dicts back to State objects
        if event_type == EVENT_STATE_CHANGED and event_data:
            for key in ("old_state", "new_state"):
                state = ha.State.from_dict(event_data[key])

                if state:
                    event_data[key] = state

        request.app[KEY_HASS].bus.async_fire(
            event_type, event_data, ha.EventOrigin.remote, self.context(request)
        )

        return self.json_message(f"Event {event_type} fired.")


class APIServicesView(HomeAssistantView):
    """View to handle Services requests."""

    url = URL_API_SERVICES
    name = "api:services"

    async def get(self, request: web.Request) -> web.Response:
        """Get registered services."""
        services = await async_services_json(request.app[KEY_HASS])
        return self.json(services)


class APIDomainServicesView(HomeAssistantView):
    """View to handle DomainServices requests."""

    url = "/api/services/{domain}/{service}"
    name = "api:domain-services"

    async def post(
        self, request: web.Request, domain: str, service: str
    ) -> web.Response:
        """Call a service.

        Returns a list of changed states.
        """
        hass = request.app[KEY_HASS]
        body = await request.text()
        try:
            data = json_loads(body) if body else None
        except ValueError:
            return self.json_message(
                "Data should be valid JSON.", HTTPStatus.BAD_REQUEST
            )

        context = self.context(request)
        if not hass.services.has_service(domain, service):
            raise HTTPBadRequest from ServiceNotFound(domain, service)

        if response_requested := "return_response" in request.query:
            if (
                hass.services.supports_response(domain, service)
                is ha.SupportsResponse.NONE
            ):
                return self.json_message(
                    "Service does not support responses. Remove return_response from request.",
                    HTTPStatus.BAD_REQUEST,
                )
        elif (
            hass.services.supports_response(domain, service) is ha.SupportsResponse.ONLY
        ):
            return self.json_message(
                "Service call requires responses but caller did not ask for responses. "
                "Add ?return_response to query parameters.",
                HTTPStatus.BAD_REQUEST,
            )

        changed_states: list[json_fragment] = []

        @ha.callback
        def _async_save_changed_entities(
            event: Event[EventStateChangedData],
        ) -> None:
            if event.context == context and (state := event.data["new_state"]):
                changed_states.append(state.json_fragment)

        cancel_listen = hass.bus.async_listen(
            EVENT_STATE_CHANGED,
            _async_save_changed_entities,
        )

        try:
            # shield the service call from cancellation on connection drop
            response = await shield(
                hass.services.async_call(
                    domain,
                    service,
                    data,  # type: ignore[arg-type]
                    blocking=True,
                    context=context,
                    return_response=response_requested,
                )
            )
        except (vol.Invalid, ServiceNotFound) as ex:
            raise HTTPBadRequest from ex
        finally:
            cancel_listen()

        if response_requested:
            return self.json(
                {"changed_states": changed_states, "service_response": response}
            )

        return self.json(changed_states)


class APIComponentsView(HomeAssistantView):
    """View to handle Components requests."""

    url = URL_API_COMPONENTS
    name = "api:components"

    @ha.callback
    def get(self, request: web.Request) -> web.Response:
        """Get current loaded components."""
        return self.json(request.app[KEY_HASS].config.components)


@lru_cache
def _cached_template(template_str: str, hass: HomeAssistant) -> template.Template:
    """Return a cached template."""
    return template.Template(template_str, hass)


class APITemplateView(HomeAssistantView):
    """View to handle Template requests."""

    url = URL_API_TEMPLATE
    name = "api:template"

    @require_admin
    async def post(self, request: web.Request) -> web.Response:
        """Render a template."""
        try:
            body = await request.text()

            data: Any = json_loads(body) if body else None

            if not isinstance(data, dict):
                return self.json_message(
                    "Template data should be a JSON object", HTTPStatus.BAD_REQUEST
                )
            tpl = _cached_template(data["template"], request.app[KEY_HASS])
            return tpl.async_render(variables=data.get("variables"), parse_result=False)  # type: ignore[no-any-return]
        except (ValueError, TemplateError) as ex:
            return self.json_message(
                f"Error rendering template: {ex}", HTTPStatus.BAD_REQUEST
            )


class APIErrorLog(HomeAssistantView):
    """View to fetch the API error log."""

    url = URL_API_ERROR_LOG
    name = "api:error_log"

    @require_admin
    async def get(self, request: web.Request) -> web.FileResponse:
        """Retrieve API error log."""
        hass = request.app[KEY_HASS]
        response = web.FileResponse(hass.data[DATA_LOGGING])
        response.enable_compression()
        return response


async def async_services_json(hass: HomeAssistant) -> list[dict[str, Any]]:
    """Generate services data to JSONify."""
    descriptions = await async_get_all_descriptions(hass)
    return [{"domain": key, "services": value} for key, value in descriptions.items()]


@ha.callback
def async_events_json(hass: HomeAssistant) -> list[dict[str, Any]]:
    """Generate event data to JSONify."""
    return [
        {"event": key, "listener_count": value}
        for key, value in hass.bus.async_listeners().items()
    ]
