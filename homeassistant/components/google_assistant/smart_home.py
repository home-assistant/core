"""Support for Google Assistant Smart Home API."""
from itertools import product
import logging

from homeassistant.util.decorator import Registry

from homeassistant.const import (
    CLOUD_NEVER_EXPOSED_ENTITIES, ATTR_ENTITY_ID)

from .const import (
    ERR_PROTOCOL_ERROR, ERR_DEVICE_OFFLINE, ERR_UNKNOWN_ERROR,
    EVENT_COMMAND_RECEIVED, EVENT_SYNC_RECEIVED, EVENT_QUERY_RECEIVED
)
from .helpers import RequestData, GoogleEntity
from .error import SmartHomeError

HANDLERS = Registry()
_LOGGER = logging.getLogger(__name__)


async def async_handle_message(hass, config, user_id, message):
    """Handle incoming API messages."""
    request_id = message.get('requestId')  # type: str

    data = RequestData(config, user_id, request_id)

    response = await _process(hass, data, message)

    if response and 'errorCode' in response['payload']:
        _LOGGER.error('Error handling message %s: %s',
                      message, response['payload'])

    return response


async def _process(hass, data, message):
    """Process a message."""
    inputs = message.get('inputs')  # type: list

    if len(inputs) != 1:
        return {
            'requestId': data.request_id,
            'payload': {'errorCode': ERR_PROTOCOL_ERROR}
        }

    handler = HANDLERS.get(inputs[0].get('intent'))

    if handler is None:
        return {
            'requestId': data.request_id,
            'payload': {'errorCode': ERR_PROTOCOL_ERROR}
        }

    try:
        result = await handler(hass, data, inputs[0].get('payload'))
    except SmartHomeError as err:
        return {
            'requestId': data.request_id,
            'payload': {'errorCode': err.code}
        }
    except Exception:  # pylint: disable=broad-except
        _LOGGER.exception('Unexpected error')
        return {
            'requestId': data.request_id,
            'payload': {'errorCode': ERR_UNKNOWN_ERROR}
        }

    if result is None:
        return None
    return {'requestId': data.request_id, 'payload': result}


@HANDLERS.register('action.devices.SYNC')
async def async_devices_sync(hass, data, payload):
    """Handle action.devices.SYNC request.

    https://developers.google.com/actions/smarthome/create-app#actiondevicessync
    """
    hass.bus.async_fire(
        EVENT_SYNC_RECEIVED,
        {'request_id': data.request_id},
        context=data.context)

    devices = []
    for state in hass.states.async_all():
        if state.entity_id in CLOUD_NEVER_EXPOSED_ENTITIES:
            continue

        if not data.config.should_expose(state):
            continue

        entity = GoogleEntity(hass, data.config, state)
        serialized = await entity.sync_serialize()

        if serialized is None:
            _LOGGER.debug("No mapping for %s domain", entity.state)
            continue

        devices.append(serialized)

    response = {
        'agentUserId': data.context.user_id,
        'devices': devices,
    }

    return response


@HANDLERS.register('action.devices.QUERY')
async def async_devices_query(hass, data, payload):
    """Handle action.devices.QUERY request.

    https://developers.google.com/actions/smarthome/create-app#actiondevicesquery
    """
    devices = {}
    for device in payload.get('devices', []):
        devid = device['id']
        state = hass.states.get(devid)

        hass.bus.async_fire(
            EVENT_QUERY_RECEIVED,
            {
                'request_id': data.request_id,
                ATTR_ENTITY_ID: devid,
            },
            context=data.context)

        if not state:
            # If we can't find a state, the device is offline
            devices[devid] = {'online': False}
            continue

        entity = GoogleEntity(hass, data.config, state)
        devices[devid] = entity.query_serialize()

    return {'devices': devices}


@HANDLERS.register('action.devices.EXECUTE')
async def handle_devices_execute(hass, data, payload):
    """Handle action.devices.EXECUTE request.

    https://developers.google.com/actions/smarthome/create-app#actiondevicesexecute
    """
    entities = {}
    results = {}

    for command in payload['commands']:
        for device, execution in product(command['devices'],
                                         command['execution']):
            entity_id = device['id']

            hass.bus.async_fire(
                EVENT_COMMAND_RECEIVED,
                {
                    'request_id': data.request_id,
                    ATTR_ENTITY_ID: entity_id,
                    'execution': execution
                },
                context=data.context)

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

                entities[entity_id] = GoogleEntity(hass, data.config, state)

            try:
                await entities[entity_id].execute(data, execution)
            except SmartHomeError as err:
                results[entity_id] = {
                    'ids': [entity_id],
                    'status': 'ERROR',
                    **err.to_response()
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


@HANDLERS.register('action.devices.DISCONNECT')
async def async_devices_disconnect(hass, data, payload):
    """Handle action.devices.DISCONNECT request.

    https://developers.google.com/actions/smarthome/create#actiondevicesdisconnect
    """
    return None


def turned_off_response(message):
    """Return a device turned off response."""
    return {
        'requestId': message.get('requestId'),
        'payload': {'errorCode': 'deviceTurnedOff'}
    }
