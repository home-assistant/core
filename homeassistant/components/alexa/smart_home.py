"""Support for alexa Smart Home Skill API."""
import asyncio
from collections import namedtuple
import logging
import math
from uuid import uuid4

import homeassistant.core as ha
from homeassistant.const import (
    ATTR_ENTITY_ID, ATTR_SUPPORTED_FEATURES, SERVICE_LOCK,
    SERVICE_MEDIA_NEXT_TRACK, SERVICE_MEDIA_PAUSE, SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_PREVIOUS_TRACK, SERVICE_MEDIA_STOP,
    SERVICE_SET_COVER_POSITION, SERVICE_TURN_OFF, SERVICE_TURN_ON,
    SERVICE_UNLOCK, SERVICE_VOLUME_SET)
from homeassistant.components import (
    alert, automation, cover, fan, group, input_boolean, light, lock,
    media_player, scene, script, switch)
import homeassistant.util.color as color_util
from homeassistant.util.decorator import Registry

HANDLERS = Registry()
_LOGGER = logging.getLogger(__name__)

API_DIRECTIVE = 'directive'
API_ENDPOINT = 'endpoint'
API_EVENT = 'event'
API_HEADER = 'header'
API_PAYLOAD = 'payload'

ATTR_ALEXA_DESCRIPTION = 'alexa_description'
ATTR_ALEXA_DISPLAY_CATEGORIES = 'alexa_display_categories'
ATTR_ALEXA_HIDDEN = 'alexa_hidden'
ATTR_ALEXA_NAME = 'alexa_name'


MAPPING_COMPONENT = {
    alert.DOMAIN: ['OTHER', ('Alexa.PowerController',), None],
    automation.DOMAIN: ['OTHER', ('Alexa.PowerController',), None],
    cover.DOMAIN: [
        'DOOR', ('Alexa.PowerController',), {
            cover.SUPPORT_SET_POSITION: 'Alexa.PercentageController',
        }
    ],
    fan.DOMAIN: [
        'OTHER', ('Alexa.PowerController',), {
            fan.SUPPORT_SET_SPEED: 'Alexa.PercentageController',
        }
    ],
    group.DOMAIN: ['OTHER', ('Alexa.PowerController',), None],
    input_boolean.DOMAIN: ['OTHER', ('Alexa.PowerController',), None],
    light.DOMAIN: [
        'LIGHT', ('Alexa.PowerController',), {
            light.SUPPORT_BRIGHTNESS: 'Alexa.BrightnessController',
            light.SUPPORT_RGB_COLOR: 'Alexa.ColorController',
            light.SUPPORT_XY_COLOR: 'Alexa.ColorController',
            light.SUPPORT_COLOR_TEMP: 'Alexa.ColorTemperatureController',
        }
    ],
    lock.DOMAIN: ['SMARTLOCK', ('Alexa.LockController',), None],
    media_player.DOMAIN: [
        'TV', ('Alexa.PowerController',), {
            media_player.SUPPORT_VOLUME_SET: 'Alexa.Speaker',
            media_player.SUPPORT_PLAY: 'Alexa.PlaybackController',
            media_player.SUPPORT_PAUSE: 'Alexa.PlaybackController',
            media_player.SUPPORT_STOP: 'Alexa.PlaybackController',
            media_player.SUPPORT_NEXT_TRACK: 'Alexa.PlaybackController',
            media_player.SUPPORT_PREVIOUS_TRACK: 'Alexa.PlaybackController',
        }
    ],
    scene.DOMAIN: ['ACTIVITY_TRIGGER', ('Alexa.SceneController',), None],
    script.DOMAIN: ['OTHER', ('Alexa.PowerController',), None],
    switch.DOMAIN: ['SWITCH', ('Alexa.PowerController',), None],
}


Config = namedtuple('AlexaConfig', 'filter')


@asyncio.coroutine
def async_handle_message(hass, config, message):
    """Handle incoming API messages."""
    assert message[API_DIRECTIVE][API_HEADER]['payloadVersion'] == '3'

    # Read head data
    message = message[API_DIRECTIVE]
    namespace = message[API_HEADER]['namespace']
    name = message[API_HEADER]['name']

    # Do we support this API request?
    funct_ref = HANDLERS.get((namespace, name))
    if not funct_ref:
        _LOGGER.warning(
            "Unsupported API request %s/%s", namespace, name)
        return api_error(message)

    return (yield from funct_ref(hass, config, message))


def api_message(request, name='Response', namespace='Alexa', payload=None):
    """Create a API formatted response message.

    Async friendly.
    """
    payload = payload or {}

    response = {
        API_EVENT: {
            API_HEADER: {
                'namespace': namespace,
                'name': name,
                'messageId': str(uuid4()),
                'payloadVersion': '3',
            },
            API_PAYLOAD: payload,
        }
    }

    # If a correlation token exsits, add it to header / Need by Async requests
    token = request[API_HEADER].get('correlationToken')
    if token:
        response[API_EVENT][API_HEADER]['correlationToken'] = token

    # Extend event with endpoint object / Need by Async requests
    if API_ENDPOINT in request:
        response[API_EVENT][API_ENDPOINT] = request[API_ENDPOINT].copy()

    return response


def api_error(request, error_type='INTERNAL_ERROR', error_message=""):
    """Create a API formatted error response.

    Async friendly.
    """
    payload = {
        'type': error_type,
        'message': error_message,
    }

    return api_message(request, name='ErrorResponse', payload=payload)


@HANDLERS.register(('Alexa.Discovery', 'Discover'))
@asyncio.coroutine
def async_api_discovery(hass, config, request):
    """Create a API formatted discovery response.

    Async friendly.
    """
    discovery_endpoints = []

    for entity in hass.states.async_all():
        if not config.filter(entity.entity_id):
            _LOGGER.debug("Not exposing %s because filtered by config",
                          entity.entity_id)
            continue

        if entity.attributes.get(ATTR_ALEXA_HIDDEN, False):
            _LOGGER.debug("Not exposing %s because alexa_hidden is true",
                          entity.entity_id)
            continue

        class_data = MAPPING_COMPONENT.get(entity.domain)

        if not class_data:
            continue

        friendly_name = entity.attributes.get(ATTR_ALEXA_NAME, entity.name)
        description = entity.attributes.get(ATTR_ALEXA_DESCRIPTION,
                                            entity.entity_id)

        # Required description as per Amazon Scene docs
        if entity.domain == scene.DOMAIN:
            scene_fmt = '{} (Scene connected via Home Assistant)'
            description = scene_fmt.format(description)

        cat_key = ATTR_ALEXA_DISPLAY_CATEGORIES
        display_categories = entity.attributes.get(cat_key, class_data[0])

        endpoint = {
            'displayCategories': [display_categories],
            'additionalApplianceDetails': {},
            'endpointId': entity.entity_id.replace('.', '#'),
            'friendlyName': friendly_name,
            'description': description,
            'manufacturerName': 'Home Assistant',
        }
        actions = set()

        # static actions
        if class_data[1]:
            actions |= set(class_data[1])

        # dynamic actions
        if class_data[2]:
            supported = entity.attributes.get(ATTR_SUPPORTED_FEATURES, 0)
            for feature, action_name in class_data[2].items():
                if feature & supported > 0:
                    actions.add(action_name)

        # Write action into capabilities
        capabilities = []
        for action in actions:
            capabilities.append({
                'type': 'AlexaInterface',
                'interface': action,
                'version': 3,
            })

        endpoint['capabilities'] = capabilities
        discovery_endpoints.append(endpoint)

    return api_message(
        request, name='Discover.Response', namespace='Alexa.Discovery',
        payload={'endpoints': discovery_endpoints})


def extract_entity(funct):
    """Decorator for extract entity object from request."""
    @asyncio.coroutine
    def async_api_entity_wrapper(hass, config, request):
        """Process a turn on request."""
        entity_id = request[API_ENDPOINT]['endpointId'].replace('#', '.')

        # extract state object
        entity = hass.states.get(entity_id)
        if not entity:
            _LOGGER.error("Can't process %s for %s",
                          request[API_HEADER]['name'], entity_id)
            return api_error(request, error_type='NO_SUCH_ENDPOINT')

        return (yield from funct(hass, config, request, entity))

    return async_api_entity_wrapper


@HANDLERS.register(('Alexa.PowerController', 'TurnOn'))
@extract_entity
@asyncio.coroutine
def async_api_turn_on(hass, config, request, entity):
    """Process a turn on request."""
    domain = entity.domain
    if entity.domain == group.DOMAIN:
        domain = ha.DOMAIN

    yield from hass.services.async_call(domain, SERVICE_TURN_ON, {
        ATTR_ENTITY_ID: entity.entity_id
    }, blocking=True)

    return api_message(request)


@HANDLERS.register(('Alexa.PowerController', 'TurnOff'))
@extract_entity
@asyncio.coroutine
def async_api_turn_off(hass, config, request, entity):
    """Process a turn off request."""
    domain = entity.domain
    if entity.domain == group.DOMAIN:
        domain = ha.DOMAIN

    yield from hass.services.async_call(domain, SERVICE_TURN_OFF, {
        ATTR_ENTITY_ID: entity.entity_id
    }, blocking=True)

    return api_message(request)


@HANDLERS.register(('Alexa.BrightnessController', 'SetBrightness'))
@extract_entity
@asyncio.coroutine
def async_api_set_brightness(hass, config, request, entity):
    """Process a set brightness request."""
    brightness = int(request[API_PAYLOAD]['brightness'])

    yield from hass.services.async_call(entity.domain, SERVICE_TURN_ON, {
        ATTR_ENTITY_ID: entity.entity_id,
        light.ATTR_BRIGHTNESS_PCT: brightness,
    }, blocking=True)

    return api_message(request)


@HANDLERS.register(('Alexa.BrightnessController', 'AdjustBrightness'))
@extract_entity
@asyncio.coroutine
def async_api_adjust_brightness(hass, config, request, entity):
    """Process a adjust brightness request."""
    brightness_delta = int(request[API_PAYLOAD]['brightnessDelta'])

    # read current state
    try:
        current = math.floor(
            int(entity.attributes.get(light.ATTR_BRIGHTNESS)) / 255 * 100)
    except ZeroDivisionError:
        current = 0

    # set brightness
    brightness = max(0, brightness_delta + current)
    yield from hass.services.async_call(entity.domain, SERVICE_TURN_ON, {
        ATTR_ENTITY_ID: entity.entity_id,
        light.ATTR_BRIGHTNESS_PCT: brightness,
    }, blocking=True)

    return api_message(request)


@HANDLERS.register(('Alexa.ColorController', 'SetColor'))
@extract_entity
@asyncio.coroutine
def async_api_set_color(hass, config, request, entity):
    """Process a set color request."""
    supported = entity.attributes.get(ATTR_SUPPORTED_FEATURES)
    rgb = color_util.color_hsb_to_RGB(
        float(request[API_PAYLOAD]['color']['hue']),
        float(request[API_PAYLOAD]['color']['saturation']),
        float(request[API_PAYLOAD]['color']['brightness'])
    )

    if supported & light.SUPPORT_RGB_COLOR > 0:
        yield from hass.services.async_call(entity.domain, SERVICE_TURN_ON, {
            ATTR_ENTITY_ID: entity.entity_id,
            light.ATTR_RGB_COLOR: rgb,
        }, blocking=True)
    else:
        xyz = color_util.color_RGB_to_xy(*rgb)
        yield from hass.services.async_call(entity.domain, SERVICE_TURN_ON, {
            ATTR_ENTITY_ID: entity.entity_id,
            light.ATTR_XY_COLOR: (xyz[0], xyz[1]),
            light.ATTR_BRIGHTNESS: xyz[2],
        }, blocking=True)

    return api_message(request)


@HANDLERS.register(('Alexa.ColorTemperatureController', 'SetColorTemperature'))
@extract_entity
@asyncio.coroutine
def async_api_set_color_temperature(hass, config, request, entity):
    """Process a set color temperature request."""
    kelvin = int(request[API_PAYLOAD]['colorTemperatureInKelvin'])

    yield from hass.services.async_call(entity.domain, SERVICE_TURN_ON, {
        ATTR_ENTITY_ID: entity.entity_id,
        light.ATTR_KELVIN: kelvin,
    }, blocking=True)

    return api_message(request)


@HANDLERS.register(
    ('Alexa.ColorTemperatureController', 'DecreaseColorTemperature'))
@extract_entity
@asyncio.coroutine
def async_api_decrease_color_temp(hass, config, request, entity):
    """Process a decrease color temperature request."""
    current = int(entity.attributes.get(light.ATTR_COLOR_TEMP))
    max_mireds = int(entity.attributes.get(light.ATTR_MAX_MIREDS))

    value = min(max_mireds, current + 50)
    yield from hass.services.async_call(entity.domain, SERVICE_TURN_ON, {
        ATTR_ENTITY_ID: entity.entity_id,
        light.ATTR_COLOR_TEMP: value,
    }, blocking=True)

    return api_message(request)


@HANDLERS.register(
    ('Alexa.ColorTemperatureController', 'IncreaseColorTemperature'))
@extract_entity
@asyncio.coroutine
def async_api_increase_color_temp(hass, config, request, entity):
    """Process a increase color temperature request."""
    current = int(entity.attributes.get(light.ATTR_COLOR_TEMP))
    min_mireds = int(entity.attributes.get(light.ATTR_MIN_MIREDS))

    value = max(min_mireds, current - 50)
    yield from hass.services.async_call(entity.domain, SERVICE_TURN_ON, {
        ATTR_ENTITY_ID: entity.entity_id,
        light.ATTR_COLOR_TEMP: value,
    }, blocking=True)

    return api_message(request)


@HANDLERS.register(('Alexa.SceneController', 'Activate'))
@extract_entity
@asyncio.coroutine
def async_api_activate(hass, config, request, entity):
    """Process a activate request."""
    yield from hass.services.async_call(entity.domain, SERVICE_TURN_ON, {
        ATTR_ENTITY_ID: entity.entity_id
    }, blocking=True)

    return api_message(request)


@HANDLERS.register(('Alexa.PercentageController', 'SetPercentage'))
@extract_entity
@asyncio.coroutine
def async_api_set_percentage(hass, config, request, entity):
    """Process a set percentage request."""
    percentage = int(request[API_PAYLOAD]['percentage'])
    service = None
    data = {ATTR_ENTITY_ID: entity.entity_id}

    if entity.domain == fan.DOMAIN:
        service = fan.SERVICE_SET_SPEED
        speed = "off"

        if percentage <= 33:
            speed = "low"
        elif percentage <= 66:
            speed = "medium"
        elif percentage <= 100:
            speed = "high"
        data[fan.ATTR_SPEED] = speed

    elif entity.domain == cover.DOMAIN:
        service = SERVICE_SET_COVER_POSITION
        data[cover.ATTR_POSITION] = percentage

    yield from hass.services.async_call(entity.domain, service,
                                        data, blocking=True)

    return api_message(request)


@HANDLERS.register(('Alexa.PercentageController', 'AdjustPercentage'))
@extract_entity
@asyncio.coroutine
def async_api_adjust_percentage(hass, config, request, entity):
    """Process a adjust percentage request."""
    percentage_delta = int(request[API_PAYLOAD]['percentageDelta'])
    service = None
    data = {ATTR_ENTITY_ID: entity.entity_id}

    if entity.domain == fan.DOMAIN:
        service = fan.SERVICE_SET_SPEED
        speed = entity.attributes.get(fan.ATTR_SPEED)

        if speed == "off":
            current = 0
        elif speed == "low":
            current = 33
        elif speed == "medium":
            current = 66
        elif speed == "high":
            current = 100

        # set percentage
        percentage = max(0, percentage_delta + current)
        speed = "off"

        if percentage <= 33:
            speed = "low"
        elif percentage <= 66:
            speed = "medium"
        elif percentage <= 100:
            speed = "high"

        data[fan.ATTR_SPEED] = speed

    elif entity.domain == cover.DOMAIN:
        service = SERVICE_SET_COVER_POSITION

        current = entity.attributes.get(cover.ATTR_POSITION)

        data[cover.ATTR_POSITION] = max(0, percentage_delta + current)

    yield from hass.services.async_call(entity.domain, service,
                                        data, blocking=True)

    return api_message(request)


@HANDLERS.register(('Alexa.LockController', 'Lock'))
@extract_entity
@asyncio.coroutine
def async_api_lock(hass, config, request, entity):
    """Process a lock request."""
    yield from hass.services.async_call(entity.domain, SERVICE_LOCK, {
        ATTR_ENTITY_ID: entity.entity_id
    }, blocking=True)

    return api_message(request)


# Not supported by Alexa yet
@HANDLERS.register(('Alexa.LockController', 'Unlock'))
@extract_entity
@asyncio.coroutine
def async_api_unlock(hass, config, request, entity):
    """Process a unlock request."""
    yield from hass.services.async_call(entity.domain, SERVICE_UNLOCK, {
        ATTR_ENTITY_ID: entity.entity_id
    }, blocking=True)

    return api_message(request)


@HANDLERS.register(('Alexa.Speaker', 'SetVolume'))
@extract_entity
@asyncio.coroutine
def async_api_set_volume(hass, config, request, entity):
    """Process a set volume request."""
    volume = round(float(request[API_PAYLOAD]['volume'] / 100), 2)

    data = {
        ATTR_ENTITY_ID: entity.entity_id,
        media_player.ATTR_MEDIA_VOLUME_LEVEL: volume,
    }

    yield from hass.services.async_call(entity.domain, SERVICE_VOLUME_SET,
                                        data, blocking=True)

    return api_message(request)


@HANDLERS.register(('Alexa.Speaker', 'AdjustVolume'))
@extract_entity
@asyncio.coroutine
def async_api_adjust_volume(hass, config, request, entity):
    """Process a adjust volume request."""
    volume_delta = int(request[API_PAYLOAD]['volume'])

    current_level = entity.attributes.get(media_player.ATTR_MEDIA_VOLUME_LEVEL)

    # read current state
    try:
        current = math.floor(int(current_level * 100))
    except ZeroDivisionError:
        current = 0

    volume = float(max(0, volume_delta + current) / 100)

    data = {
        ATTR_ENTITY_ID: entity.entity_id,
        media_player.ATTR_MEDIA_VOLUME_LEVEL: volume,
    }

    yield from hass.services.async_call(entity.domain,
                                        media_player.SERVICE_VOLUME_SET,
                                        data, blocking=True)

    return api_message(request)


@HANDLERS.register(('Alexa.Speaker', 'SetMute'))
@extract_entity
@asyncio.coroutine
def async_api_set_mute(hass, config, request, entity):
    """Process a set mute request."""
    mute = bool(request[API_PAYLOAD]['mute'])

    data = {
        ATTR_ENTITY_ID: entity.entity_id,
        media_player.ATTR_MEDIA_VOLUME_MUTED: mute,
    }

    yield from hass.services.async_call(entity.domain,
                                        media_player.SERVICE_VOLUME_MUTE,
                                        data, blocking=True)

    return api_message(request)


@HANDLERS.register(('Alexa.PlaybackController', 'Play'))
@extract_entity
@asyncio.coroutine
def async_api_play(hass, config, request, entity):
    """Process a play request."""
    data = {
        ATTR_ENTITY_ID: entity.entity_id
    }

    yield from hass.services.async_call(entity.domain, SERVICE_MEDIA_PLAY,
                                        data, blocking=True)

    return api_message(request)


@HANDLERS.register(('Alexa.PlaybackController', 'Pause'))
@extract_entity
@asyncio.coroutine
def async_api_pause(hass, config, request, entity):
    """Process a pause request."""
    data = {
        ATTR_ENTITY_ID: entity.entity_id
    }

    yield from hass.services.async_call(entity.domain, SERVICE_MEDIA_PAUSE,
                                        data, blocking=True)

    return api_message(request)


@HANDLERS.register(('Alexa.PlaybackController', 'Stop'))
@extract_entity
@asyncio.coroutine
def async_api_stop(hass, config, request, entity):
    """Process a stop request."""
    data = {
        ATTR_ENTITY_ID: entity.entity_id
    }

    yield from hass.services.async_call(entity.domain, SERVICE_MEDIA_STOP,
                                        data, blocking=True)

    return api_message(request)


@HANDLERS.register(('Alexa.PlaybackController', 'Next'))
@extract_entity
@asyncio.coroutine
def async_api_next(hass, config, request, entity):
    """Process a next request."""
    data = {
        ATTR_ENTITY_ID: entity.entity_id
    }

    yield from hass.services.async_call(entity.domain,
                                        SERVICE_MEDIA_NEXT_TRACK,
                                        data, blocking=True)

    return api_message(request)


@HANDLERS.register(('Alexa.PlaybackController', 'Previous'))
@extract_entity
@asyncio.coroutine
def async_api_previous(hass, config, request, entity):
    """Process a previous request."""
    data = {
        ATTR_ENTITY_ID: entity.entity_id
    }

    yield from hass.services.async_call(entity.domain,
                                        SERVICE_MEDIA_PREVIOUS_TRACK,
                                        data, blocking=True)

    return api_message(request)
