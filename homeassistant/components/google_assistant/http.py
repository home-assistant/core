"""
Support for Google Actions Smart Home Control.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/google_assistant/
"""
import asyncio
import logging

# Typing imports
# pylint: disable=using-constant-test,unused-import,ungrouped-imports
# if False:
from homeassistant.core import HomeAssistant  # NOQA
from aiohttp.web import Request, Response  # NOQA
from typing import Dict, Tuple, Any  # NOQA
from homeassistant.helpers.entity import Entity  # NOQA

from homeassistant.components.http import HomeAssistantView

from homeassistant.const import (HTTP_BAD_REQUEST, HTTP_UNAUTHORIZED)

from .const import (
    GOOGLE_ASSISTANT_API_ENDPOINT,
    CONF_ACCESS_TOKEN,
    DEFAULT_EXPOSE_BY_DEFAULT,
    DEFAULT_EXPOSED_DOMAINS,
    CONF_EXPOSE_BY_DEFAULT,
    CONF_EXPOSED_DOMAINS,
    ATTR_GOOGLE_ASSISTANT)
from .smart_home import entity_to_device, query_device, determine_service

_LOGGER = logging.getLogger(__name__)


class GoogleAssistantView(HomeAssistantView):
    """Handle Google Assistant requests."""

    url = GOOGLE_ASSISTANT_API_ENDPOINT
    name = 'api:google_assistant'
    requires_auth = False  # Uses access token from oauth flow

    def __init__(self, hass: HomeAssistant, cfg: Dict[str, Any]) -> None:
        """Initialize Google Assistant view."""
        super().__init__()

        self.access_token = cfg.get(CONF_ACCESS_TOKEN)
        self.expose_by_default = cfg.get(CONF_EXPOSE_BY_DEFAULT,
                                         DEFAULT_EXPOSE_BY_DEFAULT)
        self.exposed_domains = cfg.get(CONF_EXPOSED_DOMAINS,
                                       DEFAULT_EXPOSED_DOMAINS)

    def is_entity_exposed(self, entity) -> bool:
        """Determine if an entity should be exposed to Google Assistant."""
        if entity.attributes.get('view') is not None:
            # Ignore entities that are views
            return False

        domain = entity.domain.lower()
        explicit_expose = entity.attributes.get(ATTR_GOOGLE_ASSISTANT, None)

        domain_exposed_by_default = \
            self.expose_by_default and domain in self.exposed_domains

        # Expose an entity if the entity's domain is exposed by default and
        # the configuration doesn't explicitly exclude it from being
        # exposed, or if the entity is explicitly exposed
        is_default_exposed = \
            domain_exposed_by_default and explicit_expose is not False

        return is_default_exposed or explicit_expose

    @asyncio.coroutine
    def handle_sync(self, hass: HomeAssistant, request_id: str):
        """Handle SYNC action."""
        devices = []
        for entity in hass.states.async_all():
            if not self.is_entity_exposed(entity):
                continue

            device = entity_to_device(entity)
            if device is None:
                _LOGGER.warning("No mapping for %s domain", entity.domain)
                continue

            devices.append(device)

        return self.json(
            make_actions_response(request_id, {'devices': devices}))

    @asyncio.coroutine
    def handle_query(self,
                     hass: HomeAssistant,
                     request_id: str,
                     requested_devices: list):
        """Handle the QUERY action."""
        devices = {}
        for device in requested_devices:
            devid = device.get('id')
            # In theory this should never happpen
            if not devid:
                _LOGGER.error('Device missing ID: %s', device)
                continue

            state = hass.states.get(devid)
            if not state:
                # If we can't find a state, the device is offline
                devices[devid] = {'online': False}

            devices[devid] = query_device(state)

        return self.json(
            make_actions_response(request_id, {'devices': devices}))

    @asyncio.coroutine
    def handle_execute(self,
                       hass: HomeAssistant,
                       request_id: str,
                       requested_commands: list):
        """Handle the EXECUTE action."""
        commands = []
        for command in requested_commands:
            ent_ids = [ent.get('id') for ent in command.get('devices', [])]
            execution = command.get('execution')[0]
            for eid in ent_ids:
                domain = eid.split('.')[0]
                (service, service_data) = determine_service(
                    eid, execution.get('command'), execution.get('params'))
                success = yield from hass.services.async_call(
                    domain, service, service_data, blocking=True)
                result = {"ids": [eid], "states": {}}
                if success:
                    result['status'] = 'SUCCESS'
                else:
                    result['status'] = 'ERROR'
                commands.append(result)

        return self.json(
            make_actions_response(request_id, {'commands': commands}))

    @asyncio.coroutine
    def post(self, request: Request) -> Response:
        """Handle Google Assistant requests."""
        auth = request.headers.get('Authorization', None)
        if 'Bearer {}'.format(self.access_token) != auth:
            return self.json_message(
                "missing authorization", status_code=HTTP_UNAUTHORIZED)

        data = yield from request.json()  # type: dict

        inputs = data.get('inputs')  # type: list
        if len(inputs) != 1:
            _LOGGER.error('Too many inputs in request %d', len(inputs))
            return self.json_message(
                "too many inputs", status_code=HTTP_BAD_REQUEST)

        request_id = data.get('requestId')  # type: str
        intent = inputs[0].get('intent')
        payload = inputs[0].get('payload')

        hass = request.app['hass']  # type: HomeAssistant
        res = None
        if intent == 'action.devices.SYNC':
            res = yield from self.handle_sync(hass, request_id)
        elif intent == 'action.devices.QUERY':
            res = yield from self.handle_query(hass, request_id,
                                               payload.get('devices', []))
        elif intent == 'action.devices.EXECUTE':
            res = yield from self.handle_execute(hass, request_id,
                                                 payload.get('commands', []))

        if res:
            return res

        return self.json_message(
            "invalid intent", status_code=HTTP_BAD_REQUEST)


def make_actions_response(request_id: str, payload: dict) -> dict:
    """Helper to simplify format for response."""
    return {'requestId': request_id, 'payload': payload}
