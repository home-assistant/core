"""Rest API for Home Assistant."""
import asyncio
from contextlib import suppress
import json
import logging

from aiohttp import web
from aiohttp.web_exceptions import HTTPBadRequest
import async_timeout
import voluptuous as vol

from homeassistant.auth.permissions.const import POLICY_READ
from homeassistant.bootstrap import DATA_LOGGING
from homeassistant.components.http import HomeAssistantView
from homeassistant.const import (
    EVENT_HOMEASSISTANT_STOP,
    EVENT_TIME_CHANGED,
    HTTP_BAD_REQUEST,
    HTTP_CREATED,
    HTTP_NOT_FOUND,
    HTTP_OK,
    MATCH_ALL,
    URL_API,
    URL_API_COMPONENTS,
    URL_API_CONFIG,
    URL_API_DISCOVERY_INFO,
    URL_API_ERROR_LOG,
    URL_API_EVENTS,
    URL_API_SERVICES,
    URL_API_STATES,
    URL_API_STREAM,
    URL_API_TEMPLATE,
    __version__,
)
import homeassistant.core as ha
from homeassistant.exceptions import ServiceNotFound, TemplateError, Unauthorized
from homeassistant.helpers import template
from homeassistant.helpers.json import JSONEncoder
from homeassistant.helpers.network import NoURLAvailableError, get_url
from homeassistant.helpers.service import async_get_all_descriptions
from homeassistant.helpers.system_info import async_get_system_info

_LOGGER = logging.getLogger(__name__)

ATTR_BASE_URL = "base_url"
ATTR_CURRENCY = "currency"
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


async def async_setup(hass, config):
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
    name = "api:status"

    @ha.callback
    def get(self, request):
        """Retrieve if API is running."""
        return self.json_message("API running.")


class APIEventStream(HomeAssistantView):
    """View to handle EventStream requests."""

    url = URL_API_STREAM
    name = "api:stream"

    async def get(self, request):
        """Provide a streaming interface for the event bus."""
        if not request["hass_user"].is_admin:
            raise Unauthorized()
        hass = request.app["hass"]
        stop_obj = object()
        to_write = asyncio.Queue()

        restrict = request.query.get("restrict")
        if restrict:
            restrict = restrict.split(",") + [EVENT_HOMEASSISTANT_STOP]

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
                data = json.dumps(event, cls=JSONEncoder)

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
                    with async_timeout.timeout(STREAM_PING_INTERVAL):
                        payload = await to_write.get()

                    if payload is stop_obj:
                        break

                    msg = f"data: {payload}\n\n"
                    _LOGGER.debug("STREAM %s WRITING %s", id(stop_obj), msg.strip())
                    await response.write(msg.encode("UTF-8"))
                except asyncio.TimeoutError:
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
    def get(self, request):
        """Get current configuration."""
        return self.json(request.app["hass"].config.as_dict())


class APIDiscoveryView(HomeAssistantView):
    """View to provide Discovery information."""

    requires_auth = False
    url = URL_API_DISCOVERY_INFO
    name = "api:discovery"

    async def get(self, request):
        """Get discovery information."""
        hass = request.app["hass"]
        uuid = await hass.helpers.instance_id.async_get()
        system_info = await async_get_system_info(hass)

        data = {
            ATTR_UUID: uuid,
            ATTR_BASE_URL: None,
            ATTR_EXTERNAL_URL: None,
            ATTR_INTERNAL_URL: None,
            ATTR_LOCATION_NAME: hass.config.location_name,
            ATTR_INSTALLATION_TYPE: system_info[ATTR_INSTALLATION_TYPE],
            # always needs authentication
            ATTR_REQUIRES_API_PASSWORD: True,
            ATTR_VERSION: __version__,
            ATTR_CURRENCY: None,
        }

        with suppress(NoURLAvailableError):
            data["external_url"] = get_url(hass, allow_internal=False)

        with suppress(NoURLAvailableError):
            data["internal_url"] = get_url(hass, allow_external=False)

        # Set old base URL based on external or internal
        data["base_url"] = data["external_url"] or data["internal_url"]

        return self.json(data)


class APIStatesView(HomeAssistantView):
    """View to handle States requests."""

    url = URL_API_STATES
    name = "api:states"

    @ha.callback
    def get(self, request):
        """Get current states."""
        user = request["hass_user"]
        entity_perm = user.permissions.check_entity
        states = [
            state
            for state in request.app["hass"].states.async_all()
            if entity_perm(state.entity_id, "read")
        ]
        return self.json(states)


class APIEntityStateView(HomeAssistantView):
    """View to handle EntityState requests."""

    url = "/api/states/{entity_id}"
    name = "api:entity-state"

    @ha.callback
    def get(self, request, entity_id):
        """Retrieve state of entity."""
        user = request["hass_user"]
        if not user.permissions.check_entity(entity_id, POLICY_READ):
            raise Unauthorized(entity_id=entity_id)

        state = request.app["hass"].states.get(entity_id)
        if state:
            return self.json(state)
        return self.json_message("Entity not found.", HTTP_NOT_FOUND)

    async def post(self, request, entity_id):
        """Update state of entity."""
        if not request["hass_user"].is_admin:
            raise Unauthorized(entity_id=entity_id)
        hass = request.app["hass"]
        try:
            data = await request.json()
        except ValueError:
            return self.json_message("Invalid JSON specified.", HTTP_BAD_REQUEST)

        new_state = data.get("state")

        if new_state is None:
            return self.json_message("No state specified.", HTTP_BAD_REQUEST)

        attributes = data.get("attributes")
        force_update = data.get("force_update", False)

        is_new_state = hass.states.get(entity_id) is None

        # Write state
        hass.states.async_set(
            entity_id, new_state, attributes, force_update, self.context(request)
        )

        # Read the state back for our response
        status_code = HTTP_CREATED if is_new_state else HTTP_OK
        resp = self.json(hass.states.get(entity_id), status_code)

        resp.headers.add("Location", f"/api/states/{entity_id}")

        return resp

    @ha.callback
    def delete(self, request, entity_id):
        """Remove entity."""
        if not request["hass_user"].is_admin:
            raise Unauthorized(entity_id=entity_id)
        if request.app["hass"].states.async_remove(entity_id):
            return self.json_message("Entity removed.")
        return self.json_message("Entity not found.", HTTP_NOT_FOUND)


class APIEventListenersView(HomeAssistantView):
    """View to handle EventListeners requests."""

    url = URL_API_EVENTS
    name = "api:event-listeners"

    @ha.callback
    def get(self, request):
        """Get event listeners."""
        return self.json(async_events_json(request.app["hass"]))


class APIEventView(HomeAssistantView):
    """View to handle Event requests."""

    url = "/api/events/{event_type}"
    name = "api:event"

    async def post(self, request, event_type):
        """Fire events."""
        if not request["hass_user"].is_admin:
            raise Unauthorized()
        body = await request.text()
        try:
            event_data = json.loads(body) if body else None
        except ValueError:
            return self.json_message(
                "Event data should be valid JSON.", HTTP_BAD_REQUEST
            )

        if event_data is not None and not isinstance(event_data, dict):
            return self.json_message(
                "Event data should be a JSON object", HTTP_BAD_REQUEST
            )

        # Special case handling for event STATE_CHANGED
        # We will try to convert state dicts back to State objects
        if event_type == ha.EVENT_STATE_CHANGED and event_data:
            for key in ("old_state", "new_state"):
                state = ha.State.from_dict(event_data.get(key))

                if state:
                    event_data[key] = state

        request.app["hass"].bus.async_fire(
            event_type, event_data, ha.EventOrigin.remote, self.context(request)
        )

        return self.json_message(f"Event {event_type} fired.")


class APIServicesView(HomeAssistantView):
    """View to handle Services requests."""

    url = URL_API_SERVICES
    name = "api:services"

    async def get(self, request):
        """Get registered services."""
        services = await async_services_json(request.app["hass"])
        return self.json(services)


class APIDomainServicesView(HomeAssistantView):
    """View to handle DomainServices requests."""

    url = "/api/services/{domain}/{service}"
    name = "api:domain-services"

    async def post(self, request, domain, service):
        """Call a service.

        Returns a list of changed states.
        """
        hass: ha.HomeAssistant = request.app["hass"]
        body = await request.text()
        try:
            data = json.loads(body) if body else None
        except ValueError:
            return self.json_message("Data should be valid JSON.", HTTP_BAD_REQUEST)

        context = self.context(request)

        try:
            await hass.services.async_call(
                domain, service, data, blocking=True, context=context
            )
        except (vol.Invalid, ServiceNotFound) as ex:
            raise HTTPBadRequest() from ex

        changed_states = []

        for state in hass.states.async_all():
            if state.context is context:
                changed_states.append(state)

        return self.json(changed_states)


class APIComponentsView(HomeAssistantView):
    """View to handle Components requests."""

    url = URL_API_COMPONENTS
    name = "api:components"

    @ha.callback
    def get(self, request):
        """Get current loaded components."""
        return self.json(request.app["hass"].config.components)


class APITemplateView(HomeAssistantView):
    """View to handle Template requests."""

    url = URL_API_TEMPLATE
    name = "api:template"

    async def post(self, request):
        """Render a template."""
        if not request["hass_user"].is_admin:
            raise Unauthorized()
        try:
            data = await request.json()
            tpl = template.Template(data["template"], request.app["hass"])
            return tpl.async_render(variables=data.get("variables"), parse_result=False)
        except (ValueError, TemplateError) as ex:
            return self.json_message(
                f"Error rendering template: {ex}", HTTP_BAD_REQUEST
            )


class APIErrorLog(HomeAssistantView):
    """View to fetch the API error log."""

    url = URL_API_ERROR_LOG
    name = "api:error_log"

    async def get(self, request):
        """Retrieve API error log."""
        if not request["hass_user"].is_admin:
            raise Unauthorized()
        return web.FileResponse(request.app["hass"].data[DATA_LOGGING])


async def async_services_json(hass):
    """Generate services data to JSONify."""
    descriptions = await async_get_all_descriptions(hass)
    return [{"domain": key, "services": value} for key, value in descriptions.items()]


@ha.callback
def async_events_json(hass):
    """Generate event data to JSONify."""
    return [
        {"event": key, "listener_count": value}
        for key, value in hass.bus.async_listeners().items()
    ]
