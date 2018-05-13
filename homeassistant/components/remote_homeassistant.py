"""
Connect two Home Assistant instances via the Websocket API.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/remote_homeassistant/
"""

import logging
import copy
import asyncio
import aiohttp

import voluptuous as vol

import homeassistant.components.websocket_api as api
from homeassistant.core import EventOrigin, split_entity_id
from homeassistant.helpers.typing import HomeAssistantType, ConfigType
from homeassistant.const import (CONF_HOST, CONF_PORT, EVENT_CALL_SERVICE,
                                 EVENT_HOMEASSISTANT_STOP,
                                 EVENT_STATE_CHANGED, EVENT_SERVICE_REGISTERED, CONF_URL)
from homeassistant.config import DATA_CUSTOMIZE
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_INSTANCES = 'instances'
CONF_SECURE = 'secure'
CONF_API_PASSWORD = 'api_password'
CONF_SUBSCRIBE_EVENTS = 'subscribe_events'
CONF_ENTITY_PREFIX = 'entity_prefix'

DOMAIN = 'remote_homeassistant'

DEFAULT_SUBSCRIBED_EVENTS = [EVENT_STATE_CHANGED,
                             EVENT_SERVICE_REGISTERED]
DEFAULT_ENTITY_PREFIX = ''

INSTANCES_SCHEMA = vol.Schema({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_PORT, default=8123): cv.port,
    vol.Optional(CONF_SECURE, default=False): cv.boolean,
    vol.Optional(CONF_API_PASSWORD): cv.string,
    vol.Optional(CONF_SUBSCRIBE_EVENTS,
                 default=DEFAULT_SUBSCRIBED_EVENTS): cv.ensure_list,
    vol.Optional(CONF_ENTITY_PREFIX, default=DEFAULT_ENTITY_PREFIX): cv.string,
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_INSTANCES): [INSTANCES_SCHEMA],
    }),
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass: HomeAssistantType, config: ConfigType):
    """Set up the remote_homeassistant component."""
    conf = config.get(DOMAIN)

    for instance in conf.get(CONF_INSTANCES):
        connection = RemoteConnection(hass, instance)
        asyncio.ensure_future(connection.async_connect())

    return True


class RemoteConnection(object):
    """A Websocket connection to a remote home-assistant instance."""

    def __init__(self, hass, conf):
        """Initialize the connection."""
        self._hass = hass
        self._host = conf.get(CONF_HOST)
        self._port = conf.get(CONF_PORT)
        self._secure = conf.get(CONF_SECURE)
        self._password = conf.get(CONF_API_PASSWORD)
        self._subscribe_events = conf.get(CONF_SUBSCRIBE_EVENTS)
        self._entity_prefix = conf.get(CONF_ENTITY_PREFIX)

        self._connection = None
        self._entities = set()
        self._handlers = {}

        self.__id = 1

    async def async_connect(self):
        """Connect to remote home-assistant websocket..."""
        url = '%s://%s:%s/api/websocket' % (
            'wss' if self._secure else 'ws', self._host, self._port)

        session = async_get_clientsession(self._hass)

        while True:
            try:
                _LOGGER.info('Connecting to %s', url)
                self._connection = await session.ws_connect(url)
            except aiohttp.client_exceptions.ClientError as err:
                _LOGGER.error(
                    'Could not connect to %s, retry in 10 seconds...', url)
                await asyncio.sleep(10)
            else:
                _LOGGER.info(
                    'Connected to home-assistant websocket at %s', url)
                break

        async def stop():
            """Close connection."""
            if self._connection is not None:
                await self._connection.close()

        self._hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, stop)

        asyncio.ensure_future(self._recv())

    def _next_id(self):
        _id = self.__id
        self.__id += 1
        return _id

    async def _call(self, callback, message_type, **extra_args):
        _id = self._next_id()
        self._handlers[_id] = callback
        try:
            await self._connection.send_json(
                {'id': _id, 'type': message_type, **extra_args})
        except aiohttp.client_exceptions.ClientError as err:
            _LOGGER.error('remote websocket connection closed: %s', err)
            await self._disconnected()

    async def _disconnected(self):
        # Remove all published entries
        for entity in self._entities:
            self._hass.states.async_remove(entity)
        self._entities = set()
        asyncio.ensure_future(self.async_connect())

    async def _recv(self):
        while not self._connection.closed:
            try:
                data = await self._connection.receive()
            except aiohttp.client_exceptions.ClientError as err:
                _LOGGER.error('remote websocket connection closed: %s', err)
                await self._disconnected()
                return

            if not data:
                return

            message = data.json()
            _LOGGER.debug('received: %s', message)

            if message['type'] == api.TYPE_AUTH_OK:
                await self._init()

            elif message['type'] == api.TYPE_AUTH_REQUIRED:
                if not self._password:
                    _LOGGER.error('Password required, but not provided')
                    return
                data = {'type': api.TYPE_AUTH, 'api_password': self._password}
                await self._connection.send_json(data)

            elif message['type'] == api.TYPE_AUTH_INVALID:
                _LOGGER.error('Auth invalid, check your API password')
                await self._connection.close()
                return

            else:
                callback = self._handlers.get(message['id'])
                if callback is not None:
                    callback(message)

    async def _init(self):
        async def forward_event(event):
            """Send local event to remote instance.

            The affected entity_id has to origin from that remote instance,
            otherwise the event is dicarded.
            """
            event_data = event.data
            service_data = event_data['service_data']
            entity_ids = service_data.get('entity_id', None)

            if not entity_ids:
                return

            if isinstance(entity_ids, str):
                entity_ids = (entity_ids.lower(),)

            entity_ids = self._entities.intersection(entity_ids)

            if not entity_ids:
                return

            if self._entity_prefix:
                def _remove_prefix(entity_id):
                    domain, object_id = split_entity_id(entity_id)
                    object_id = object_id.replace(self._entity_prefix, '', 1)
                    return domain + '.' + object_id
                entity_ids = {_remove_prefix(entity_id)
                              for entity_id in entity_ids}

            event_data = copy.deepcopy(event_data)
            event_data['service_data']['entity_id'] = list(entity_ids)

            # Remove service_call_id parameter - websocket API
            # doesn't accept that one
            event_data.pop('service_call_id', None)

            _id = self._next_id()
            data = {
                'id': _id,
                'type': event.event_type,
                **event_data
            }

            _LOGGER.debug('forward event: %s', data)

            await self._connection.send_json(data)

        def state_changed(entity_id, state, attr):
            """Publish remote state change on local instance."""
            if self._entity_prefix:
                domain, object_id = split_entity_id(entity_id)
                object_id = self._entity_prefix + object_id
                entity_id = domain + '.' + object_id

            # Add local customization data
            if DATA_CUSTOMIZE in self._hass.data:
                attr.update(self._hass.data[DATA_CUSTOMIZE].get(entity_id))

            self._entities.add(entity_id)
            self._hass.states.async_set(entity_id, state, attr)

        def fire_event(message):
            """Publish remove event on local instance."""
            if message['type'] == 'result':
                return

            if message['type'] != 'event':
                return

            if message['event']['event_type'] == 'state_changed':
                entity_id = message['event']['data']['entity_id']
                state = message['event']['data']['new_state']['state']
                attr = message['event']['data']['new_state']['attributes']
                state_changed(entity_id, state, attr)
            else:
                event = message['event']
                self._hass.bus.async_fire(
                    event_type=event['event_type'],
                    event_data=event['data'],
                    origin=EventOrigin.remote
                )

        def got_states(message):
            """Called when list of remote states is available."""
            for entity in message['result']:
                entity_id = entity['entity_id']
                state = entity['state']
                attributes = entity['attributes']

                state_changed(entity_id, state, attributes)

        self._hass.bus.async_listen(EVENT_CALL_SERVICE, forward_event)

        for event in self._subscribe_events:
            await self._call(fire_event, 'subscribe_events', event_type=event)

        await self._call(got_states, 'get_states')
