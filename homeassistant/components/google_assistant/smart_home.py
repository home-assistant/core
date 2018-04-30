"""Support for Google Assistant Smart Home API."""
import collections
from itertools import product
import logging

# Typing imports
# pylint: disable=using-constant-test,unused-import,ungrouped-imports
# if False:
from aiohttp.web import Request, Response  # NOQA
from typing import Dict, Tuple, Any, Optional  # NOQA
from homeassistant.helpers.entity import Entity  # NOQA
from homeassistant.core import HomeAssistant  # NOQA
from homeassistant.util.unit_system import UnitSystem  # NOQA
from homeassistant.util.decorator import Registry

from homeassistant.core import callback
from homeassistant.const import (
    CONF_NAME, STATE_UNAVAILABLE, ATTR_SUPPORTED_FEATURES)
from homeassistant.components import (
    climate,
    cover,
    fan,
    group,
    input_boolean,
    light,
    media_player,
    scene,
    script,
    switch,
)

from . import trait
from .const import (
    TYPE_LIGHT, TYPE_SCENE, TYPE_SWITCH, TYPE_THERMOSTAT,
    CONF_ALIASES, CONF_ROOM_HINT,
    ERR_NOT_SUPPORTED, ERR_PROTOCOL_ERROR, ERR_DEVICE_OFFLINE,
    ERR_UNKNOWN_ERROR
)
from .helpers import SmartHomeError

HANDLERS = Registry()
_LOGGER = logging.getLogger(__name__)

DOMAIN_TO_GOOGLE_TYPES = {
    climate.DOMAIN: TYPE_THERMOSTAT,
    cover.DOMAIN: TYPE_SWITCH,
    fan.DOMAIN: TYPE_SWITCH,
    group.DOMAIN: TYPE_SWITCH,
    input_boolean.DOMAIN: TYPE_SWITCH,
    light.DOMAIN: TYPE_LIGHT,
    media_player.DOMAIN: TYPE_SWITCH,
    scene.DOMAIN: TYPE_SCENE,
    script.DOMAIN: TYPE_SCENE,
    switch.DOMAIN: TYPE_SWITCH,
}


def deep_update(target, source):
    """Update a nested dictionary with another nested dictionary."""
    for key, value in source.items():
        if isinstance(value, collections.Mapping):
            target[key] = deep_update(target.get(key, {}), value)
        else:
            target[key] = value
    return target


class _GoogleEntity:
    """Adaptation of Entity expressed in Google's terms."""

    def __init__(self, hass, config, state):
        self.hass = hass
        self.config = config
        self.state = state

    @property
    def entity_id(self):
        """Return entity ID."""
        return self.state.entity_id

    @callback
    def traits(self):
        """Return traits for entity."""
        state = self.state
        domain = state.domain
        features = state.attributes.get(ATTR_SUPPORTED_FEATURES, 0)

        return [Trait(state) for Trait in trait.TRAITS
                if Trait.supported(domain, features)]

    @callback
    def sync_serialize(self):
        """Serialize entity for a SYNC response.

        https://developers.google.com/actions/smarthome/create-app#actiondevicessync
        """
        state = self.state

        # When a state is unavailable, the attributes that describe
        # capabilities will be stripped. For example, a light entity will miss
        # the min/max mireds. Therefore they will be excluded from a sync.
        if state.state == STATE_UNAVAILABLE:
            return None

        entity_config = self.config.entity_config.get(state.entity_id, {})
        name = (entity_config.get(CONF_NAME) or state.name).strip()

        # If an empty string
        if not name:
            return None

        traits = self.traits()

        # Found no supported traits for this entity
        if not traits:
            return None

        device = {
            'id': state.entity_id,
            'name': {
                'name': name
            },
            'attributes': {},
            'traits': [trait.name for trait in traits],
            'willReportState': False,
            'type': DOMAIN_TO_GOOGLE_TYPES[state.domain],
        }

        # use aliases
        aliases = entity_config.get(CONF_ALIASES)
        if aliases:
            device['name']['nicknames'] = aliases

        # add room hint if annotated
        room = entity_config.get(CONF_ROOM_HINT)
        if room:
            device['roomHint'] = room

        for trt in traits:
            device['attributes'].update(trt.sync_attributes())

        return device

    @callback
    def query_serialize(self):
        """Serialize entity for a QUERY response.

        https://developers.google.com/actions/smarthome/create-app#actiondevicesquery
        """
        state = self.state

        if state.state == STATE_UNAVAILABLE:
            return {'online': False}

        attrs = {'online': True}

        for trt in self.traits():
            deep_update(attrs, trt.query_attributes())

        return attrs

    async def execute(self, command, params):
        """Execute a command.

        https://developers.google.com/actions/smarthome/create-app#actiondevicesexecute
        """
        executed = False
        for trt in self.traits():
            if trt.can_execute(command, params):
                await trt.execute(self.hass, command, params)
                executed = True
                break

        if not executed:
            raise SmartHomeError(
                ERR_NOT_SUPPORTED,
                'Unable to execute {} for {}'.format(command,
                                                     self.state.entity_id))

    @callback
    def async_update(self):
        """Update the entity with latest info from Home Assistant."""
        self.state = self.hass.states.get(self.entity_id)


async def async_handle_message(hass, config, message):
    """Handle incoming API messages."""
    response = await _process(hass, config, message)

    if 'errorCode' in response['payload']:
        _LOGGER.error('Error handling message %s: %s',
                      message, response['payload'])

    return response


async def _process(hass, config, message):
    """Process a message."""
    request_id = message.get('requestId')  # type: str
    inputs = message.get('inputs')  # type: list

    if len(inputs) != 1:
        return {
            'requestId': request_id,
            'payload': {'errorCode': ERR_PROTOCOL_ERROR}
        }

    handler = HANDLERS.get(inputs[0].get('intent'))

    if handler is None:
        return {
            'requestId': request_id,
            'payload': {'errorCode': ERR_PROTOCOL_ERROR}
        }

    try:
        result = await handler(hass, config, inputs[0].get('payload'))
        return {'requestId': request_id, 'payload': result}
    except SmartHomeError as err:
        return {
            'requestId': request_id,
            'payload': {'errorCode': err.code}
        }
    except Exception as err:  # pylint: disable=broad-except
        _LOGGER.exception('Unexpected error')
        return {
            'requestId': request_id,
            'payload': {'errorCode': ERR_UNKNOWN_ERROR}
        }


@HANDLERS.register('action.devices.SYNC')
async def async_devices_sync(hass, config, payload):
    """Handle action.devices.SYNC request.

    https://developers.google.com/actions/smarthome/create-app#actiondevicessync
    """
    devices = []
    for state in hass.states.async_all():
        if not config.should_expose(state):
            continue

        entity = _GoogleEntity(hass, config, state)
        serialized = entity.sync_serialize()

        if serialized is None:
            _LOGGER.debug("No mapping for %s domain", entity.state)
            continue

        devices.append(serialized)

    return {
        'agentUserId': config.agent_user_id,
        'devices': devices,
    }


@HANDLERS.register('action.devices.QUERY')
async def async_devices_query(hass, config, payload):
    """Handle action.devices.QUERY request.

    https://developers.google.com/actions/smarthome/create-app#actiondevicesquery
    """
    devices = {}
    for device in payload.get('devices', []):
        devid = device['id']
        state = hass.states.get(devid)

        if not state:
            # If we can't find a state, the device is offline
            devices[devid] = {'online': False}
            continue

        devices[devid] = _GoogleEntity(hass, config, state).query_serialize()

    return {'devices': devices}


@HANDLERS.register('action.devices.EXECUTE')
async def handle_devices_execute(hass, config, payload):
    """Handle action.devices.EXECUTE request.

    https://developers.google.com/actions/smarthome/create-app#actiondevicesexecute
    """
    entities = {}
    results = {}

    for command in payload['commands']:
        for device, execution in product(command['devices'],
                                         command['execution']):
            entity_id = device['id']

            # Happens if error occurred. Skip entity for further processing
            if entity_id in results:
                continue

            if entity_id not in entities:
                state = hass.states.get(entity_id)

                if state is None:
                    results[entity_id] = {
                        'ids': [entity_id],
                        'status': 'ERROR',
                        'errorCode': ERR_DEVICE_OFFLINE
                    }
                    continue

                entities[entity_id] = _GoogleEntity(hass, config, state)

            try:
                await entities[entity_id].execute(execution['command'],
                                                  execution.get('params', {}))
            except SmartHomeError as err:
                results[entity_id] = {
                    'ids': [entity_id],
                    'status': 'ERROR',
                    'errorCode': err.code
                }

    final_results = list(results.values())

    for entity in entities.values():
        if entity.entity_id in results:
            continue

        entity.async_update()

        final_results.append({
            'ids': [entity.entity_id],
            'status': 'SUCCESS',
            'states': entity.query_serialize(),
        })

    return {'commands': final_results}
