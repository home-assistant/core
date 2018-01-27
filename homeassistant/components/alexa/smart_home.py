"""Support for alexa Smart Home Skill API."""
import asyncio
import logging
import math
from datetime import datetime
from uuid import uuid4

from homeassistant.components import (
    alert, automation, cover, fan, group, input_boolean, light, lock,
    media_player, scene, script, switch, http, sensor)
import homeassistant.core as ha
import homeassistant.util.color as color_util
from homeassistant.util.decorator import Registry
from homeassistant.const import (
    ATTR_ENTITY_ID, ATTR_SUPPORTED_FEATURES, CONF_NAME, SERVICE_LOCK,
    SERVICE_MEDIA_NEXT_TRACK, SERVICE_MEDIA_PAUSE, SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_PREVIOUS_TRACK, SERVICE_MEDIA_STOP,
    SERVICE_SET_COVER_POSITION, SERVICE_TURN_OFF, SERVICE_TURN_ON,
    SERVICE_UNLOCK, SERVICE_VOLUME_SET, TEMP_FAHRENHEIT, TEMP_CELSIUS,
    CONF_UNIT_OF_MEASUREMENT)
from .const import CONF_FILTER, CONF_ENTITY_CONFIG

_LOGGER = logging.getLogger(__name__)

API_DIRECTIVE = 'directive'
API_ENDPOINT = 'endpoint'
API_EVENT = 'event'
API_CONTEXT = 'context'
API_HEADER = 'header'
API_PAYLOAD = 'payload'

API_TEMP_UNITS = {
    TEMP_FAHRENHEIT: 'FAHRENHEIT',
    TEMP_CELSIUS: 'CELSIUS',
}

SMART_HOME_HTTP_ENDPOINT = '/api/alexa/smart_home'

CONF_DESCRIPTION = 'description'
CONF_DISPLAY_CATEGORIES = 'display_categories'

HANDLERS = Registry()


class _DisplayCategory(object):
    """Possible display categories for Discovery response.

    https://developer.amazon.com/docs/device-apis/alexa-discovery.html#display-categories
    """

    # Describes a combination of devices set to a specific state, when the
    # state change must occur in a specific order. For example, a "watch
    # Neflix" scene might require the: 1. TV to be powered on & 2. Input set to
    # HDMI1.    Applies to Scenes
    ACTIVITY_TRIGGER = "ACTIVITY_TRIGGER"

    # Indicates media devices with video or photo capabilities.
    CAMERA = "CAMERA"

    # Indicates a door.
    DOOR = "DOOR"

    # Indicates light sources or fixtures.
    LIGHT = "LIGHT"

    # An endpoint that cannot be described in on of the other categories.
    OTHER = "OTHER"

    # Describes a combination of devices set to a specific state, when the
    # order of the state change is not important. For example a bedtime scene
    # might include turning off lights and lowering the thermostat, but the
    # order is unimportant.    Applies to Scenes
    SCENE_TRIGGER = "SCENE_TRIGGER"

    # Indicates an endpoint that locks.
    SMARTLOCK = "SMARTLOCK"

    # Indicates modules that are plugged into an existing electrical outlet.
    # Can control a variety of devices.
    SMARTPLUG = "SMARTPLUG"

    # Indicates the endpoint is a speaker or speaker system.
    SPEAKER = "SPEAKER"

    # Indicates in-wall switches wired to the electrical system.  Can control a
    # variety of devices.
    SWITCH = "SWITCH"

    # Indicates endpoints that report the temperature only.
    TEMPERATURE_SENSOR = "TEMPERATURE_SENSOR"

    # Indicates endpoints that control temperature, stand-alone air
    # conditioners, or heaters with direct temperature control.
    THERMOSTAT = "THERMOSTAT"

    # Indicates the endpoint is a television.
    # pylint: disable=invalid-name
    TV = "TV"


def _capability(interface,
                version=3,
                supports_deactivation=None,
                retrievable=None,
                properties_supported=None,
                cap_type='AlexaInterface'):
    """Return a Smart Home API capability object.

    https://developer.amazon.com/docs/device-apis/alexa-discovery.html#capability-object

    There are some additional fields allowed but not implemented here since
    we've no use case for them yet:

      - proactively_reported

    `supports_deactivation` applies only to scenes.
    """
    result = {
        'type': cap_type,
        'interface': interface,
        'version': version,
    }

    if supports_deactivation is not None:
        result['supportsDeactivation'] = supports_deactivation

    if retrievable is not None:
        result['retrievable'] = retrievable

    if properties_supported is not None:
        result['properties'] = {'supported': properties_supported}

    return result


class _EntityCapabilities(object):
    def __init__(self, config, entity):
        self.config = config
        self.entity = entity

    def display_categories(self):
        """Return a list of display categories."""
        entity_conf = self.config.entity_config.get(self.entity.entity_id, {})
        if CONF_DISPLAY_CATEGORIES in entity_conf:
            return [entity_conf[CONF_DISPLAY_CATEGORIES]]
        return self.default_display_categories()

    def default_display_categories(self):
        """Return a list of default display categories.

        This can be overridden by the user in the Home Assistant configuration.

        See also _DisplayCategory.
        """
        raise NotImplementedError

    def capabilities(self):
        """Return a list of supported capabilities.

        If the returned list is empty, the entity will not be discovered.

        You might find _capability() useful.
        """
        raise NotImplementedError


class _GenericCapabilities(_EntityCapabilities):
    """A generic, on/off device.

    The choice of last resort.
    """

    def default_display_categories(self):
        return [_DisplayCategory.OTHER]

    def capabilities(self):
        return [_capability('Alexa.PowerController')]


class _SwitchCapabilities(_EntityCapabilities):
    def default_display_categories(self):
        return [_DisplayCategory.SWITCH]

    def capabilities(self):
        return [_capability('Alexa.PowerController')]


class _CoverCapabilities(_EntityCapabilities):
    def default_display_categories(self):
        return [_DisplayCategory.DOOR]

    def capabilities(self):
        capabilities = [_capability('Alexa.PowerController')]
        supported = self.entity.attributes.get(ATTR_SUPPORTED_FEATURES, 0)
        if supported & cover.SUPPORT_SET_POSITION:
            capabilities.append(_capability('Alexa.PercentageController'))
        return capabilities


class _LightCapabilities(_EntityCapabilities):
    def default_display_categories(self):
        return [_DisplayCategory.LIGHT]

    def capabilities(self):
        capabilities = [_capability('Alexa.PowerController')]
        supported = self.entity.attributes.get(ATTR_SUPPORTED_FEATURES, 0)
        if supported & light.SUPPORT_BRIGHTNESS:
            capabilities.append(_capability('Alexa.BrightnessController'))
        if supported & light.SUPPORT_RGB_COLOR:
            capabilities.append(_capability('Alexa.ColorController'))
        if supported & light.SUPPORT_XY_COLOR:
            capabilities.append(_capability('Alexa.ColorController'))
        if supported & light.SUPPORT_COLOR_TEMP:
            capabilities.append(
                _capability('Alexa.ColorTemperatureController'))
        return capabilities


class _FanCapabilities(_EntityCapabilities):
    def default_display_categories(self):
        return [_DisplayCategory.OTHER]

    def capabilities(self):
        capabilities = [_capability('Alexa.PowerController')]
        supported = self.entity.attributes.get(ATTR_SUPPORTED_FEATURES, 0)
        if supported & fan.SUPPORT_SET_SPEED:
            capabilities.append(_capability('Alexa.PercentageController'))
        return capabilities


class _LockCapabilities(_EntityCapabilities):
    def default_display_categories(self):
        return [_DisplayCategory.SMARTLOCK]

    def capabilities(self):
        return [_capability('Alexa.LockController')]


class _MediaPlayerCapabilities(_EntityCapabilities):
    def default_display_categories(self):
        return [_DisplayCategory.TV]

    def capabilities(self):
        capabilities = [_capability('Alexa.PowerController')]
        supported = self.entity.attributes.get(ATTR_SUPPORTED_FEATURES, 0)
        if supported & media_player.SUPPORT_VOLUME_SET:
            capabilities.append(_capability('Alexa.Speaker'))

        playback_features = (media_player.SUPPORT_PLAY |
                             media_player.SUPPORT_PAUSE |
                             media_player.SUPPORT_STOP |
                             media_player.SUPPORT_NEXT_TRACK |
                             media_player.SUPPORT_PREVIOUS_TRACK)
        if supported & playback_features:
            capabilities.append(_capability('Alexa.PlaybackController'))

        return capabilities


class _SceneCapabilities(_EntityCapabilities):
    def default_display_categories(self):
        return [_DisplayCategory.SCENE_TRIGGER]

    def capabilities(self):
        return [_capability('Alexa.SceneController')]


class _ScriptCapabilities(_EntityCapabilities):
    def default_display_categories(self):
        return [_DisplayCategory.ACTIVITY_TRIGGER]

    def capabilities(self):
        can_cancel = bool(self.entity.attributes.get('can_cancel'))
        return [_capability('Alexa.SceneController',
                            supports_deactivation=can_cancel)]


class _GroupCapabilities(_EntityCapabilities):
    def default_display_categories(self):
        return [_DisplayCategory.SCENE_TRIGGER]

    def capabilities(self):
        return [_capability('Alexa.SceneController',
                            supports_deactivation=True)]


class _SensorCapabilities(_EntityCapabilities):
    def default_display_categories(self):
        # although there are other kinds of sensors, all but temperature
        # sensors are currently ignored.
        return [_DisplayCategory.TEMPERATURE_SENSOR]

    def capabilities(self):
        capabilities = []

        attrs = self.entity.attributes
        if attrs.get(CONF_UNIT_OF_MEASUREMENT) in (
                TEMP_FAHRENHEIT,
                TEMP_CELSIUS,
        ):
            capabilities.append(_capability(
                'Alexa.TemperatureSensor',
                retrievable=True,
                properties_supported=[{'name': 'temperature'}]))

        return capabilities


class _UnknownEntityDomainError(Exception):
    pass


def _capabilities_for_entity(config, entity):
    """Return an _EntityCapabilities appropriate for given entity.

    raises _UnknownEntityDomainError if the given domain is unsupported.
    """
    if entity.domain not in _CAPABILITIES_FOR_DOMAIN:
        raise _UnknownEntityDomainError()
    return _CAPABILITIES_FOR_DOMAIN[entity.domain](config, entity)


_CAPABILITIES_FOR_DOMAIN = {
    alert.DOMAIN: _GenericCapabilities,
    automation.DOMAIN: _GenericCapabilities,
    cover.DOMAIN: _CoverCapabilities,
    fan.DOMAIN: _FanCapabilities,
    group.DOMAIN: _GroupCapabilities,
    input_boolean.DOMAIN: _GenericCapabilities,
    light.DOMAIN: _LightCapabilities,
    lock.DOMAIN: _LockCapabilities,
    media_player.DOMAIN: _MediaPlayerCapabilities,
    scene.DOMAIN: _SceneCapabilities,
    script.DOMAIN: _ScriptCapabilities,
    switch.DOMAIN: _SwitchCapabilities,
    sensor.DOMAIN: _SensorCapabilities,
}


class _Cause(object):
    """Possible causes for property changes.

    https://developer.amazon.com/docs/smarthome/state-reporting-for-a-smart-home-skill.html#cause-object
    """

    # Indicates that the event was caused by a customer interaction with an
    # application. For example, a customer switches on a light, or locks a door
    # using the Alexa app or an app provided by a device vendor.
    APP_INTERACTION = 'APP_INTERACTION'

    # Indicates that the event was caused by a physical interaction with an
    # endpoint. For example manually switching on a light or manually locking a
    # door lock
    PHYSICAL_INTERACTION = 'PHYSICAL_INTERACTION'

    # Indicates that the event was caused by the periodic poll of an appliance,
    # which found a change in value. For example, you might poll a temperature
    # sensor every hour, and send the updated temperature to Alexa.
    PERIODIC_POLL = 'PERIODIC_POLL'

    # Indicates that the event was caused by the application of a device rule.
    # For example, a customer configures a rule to switch on a light if a
    # motion sensor detects motion. In this case, Alexa receives an event from
    # the motion sensor, and another event from the light to indicate that its
    # state change was caused by the rule.
    RULE_TRIGGER = 'RULE_TRIGGER'

    # Indicates that the event was caused by a voice interaction with Alexa.
    # For example a user speaking to their Echo device.
    VOICE_INTERACTION = 'VOICE_INTERACTION'


class Config:
    """Hold the configuration for Alexa."""

    def __init__(self, should_expose, entity_config=None):
        """Initialize the configuration."""
        self.should_expose = should_expose
        self.entity_config = entity_config or {}


@ha.callback
def async_setup(hass, config):
    """Activate Smart Home functionality of Alexa component.

    This is optional, triggered by having a `smart_home:` sub-section in the
    alexa configuration.

    Even if that's disabled, the functionality in this module may still be used
    by the cloud component which will call async_handle_message directly.
    """
    smart_home_config = Config(
        should_expose=config[CONF_FILTER],
        entity_config=config.get(CONF_ENTITY_CONFIG),
    )
    hass.http.register_view(SmartHomeView(smart_home_config))


class SmartHomeView(http.HomeAssistantView):
    """Expose Smart Home v3 payload interface via HTTP POST."""

    url = SMART_HOME_HTTP_ENDPOINT
    name = 'api:alexa:smart_home'

    def __init__(self, smart_home_config):
        """Initialize."""
        self.smart_home_config = smart_home_config

    @asyncio.coroutine
    def post(self, request):
        """Handle Alexa Smart Home requests.

        The Smart Home API requires the endpoint to be implemented in AWS
        Lambda, which will need to forward the requests to here and pass back
        the response.
        """
        hass = request.app['hass']
        message = yield from request.json()

        _LOGGER.debug("Received Alexa Smart Home request: %s", message)

        response = yield from async_handle_message(
            hass, self.smart_home_config, message)
        _LOGGER.debug("Sending Alexa Smart Home response: %s", response)
        return b'' if response is None else self.json(response)


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


def api_message(request,
                name='Response',
                namespace='Alexa',
                payload=None,
                context=None):
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

    if context is not None:
        response[API_CONTEXT] = context

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
        if not config.should_expose(entity.entity_id):
            _LOGGER.debug("Not exposing %s because filtered by config",
                          entity.entity_id)
            continue

        try:
            entity_capabilities = _capabilities_for_entity(config, entity)
        except _UnknownEntityDomainError:
            continue

        entity_conf = config.entity_config.get(entity.entity_id, {})

        friendly_name = entity_conf.get(CONF_NAME, entity.name)
        description = entity_conf.get(CONF_DESCRIPTION, entity.entity_id)

        # Required description as per Amazon Scene docs
        if entity.domain == scene.DOMAIN:
            scene_fmt = '{} (Scene connected via Home Assistant)'
            description = scene_fmt.format(description)

        endpoint = {
            'displayCategories': entity_capabilities.display_categories(),
            'additionalApplianceDetails': {},
            'endpointId': entity.entity_id.replace('.', '#'),
            'friendlyName': friendly_name,
            'description': description,
            'manufacturerName': 'Home Assistant',
        }

        alexa_capabilities = entity_capabilities.capabilities()
        if not alexa_capabilities:
            _LOGGER.debug("Not exposing %s because it has no capabilities",
                          entity.entity_id)
            continue
        endpoint['capabilities'] = alexa_capabilities
        discovery_endpoints.append(endpoint)

    return api_message(
        request, name='Discover.Response', namespace='Alexa.Discovery',
        payload={'endpoints': discovery_endpoints})


def extract_entity(funct):
    """Decorate for extract entity object from request."""
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

    service = SERVICE_TURN_ON
    if entity.domain == cover.DOMAIN:
        service = cover.SERVICE_OPEN_COVER

    yield from hass.services.async_call(domain, service, {
        ATTR_ENTITY_ID: entity.entity_id
    }, blocking=False)

    return api_message(request)


@HANDLERS.register(('Alexa.PowerController', 'TurnOff'))
@extract_entity
@asyncio.coroutine
def async_api_turn_off(hass, config, request, entity):
    """Process a turn off request."""
    domain = entity.domain
    if entity.domain == group.DOMAIN:
        domain = ha.DOMAIN

    service = SERVICE_TURN_OFF
    if entity.domain == cover.DOMAIN:
        service = cover.SERVICE_CLOSE_COVER

    yield from hass.services.async_call(domain, service, {
        ATTR_ENTITY_ID: entity.entity_id
    }, blocking=False)

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
    }, blocking=False)

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
    }, blocking=False)

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
        }, blocking=False)
    else:
        xyz = color_util.color_RGB_to_xy(*rgb)
        yield from hass.services.async_call(entity.domain, SERVICE_TURN_ON, {
            ATTR_ENTITY_ID: entity.entity_id,
            light.ATTR_XY_COLOR: (xyz[0], xyz[1]),
            light.ATTR_BRIGHTNESS: xyz[2],
        }, blocking=False)

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
    }, blocking=False)

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
    }, blocking=False)

    return api_message(request)


@HANDLERS.register(
    ('Alexa.ColorTemperatureController', 'IncreaseColorTemperature'))
@extract_entity
@asyncio.coroutine
def async_api_increase_color_temp(hass, config, request, entity):
    """Process an increase color temperature request."""
    current = int(entity.attributes.get(light.ATTR_COLOR_TEMP))
    min_mireds = int(entity.attributes.get(light.ATTR_MIN_MIREDS))

    value = max(min_mireds, current - 50)
    yield from hass.services.async_call(entity.domain, SERVICE_TURN_ON, {
        ATTR_ENTITY_ID: entity.entity_id,
        light.ATTR_COLOR_TEMP: value,
    }, blocking=False)

    return api_message(request)


@HANDLERS.register(('Alexa.SceneController', 'Activate'))
@extract_entity
@asyncio.coroutine
def async_api_activate(hass, config, request, entity):
    """Process an activate request."""
    if entity.domain == group.DOMAIN:
        domain = ha.DOMAIN
    else:
        domain = entity.domain

    yield from hass.services.async_call(domain, SERVICE_TURN_ON, {
        ATTR_ENTITY_ID: entity.entity_id
    }, blocking=False)

    payload = {
        'cause': {'type': _Cause.VOICE_INTERACTION},
        'timestamp': '%sZ' % (datetime.utcnow().isoformat(),)
    }

    return api_message(
        request,
        name='ActivationStarted',
        namespace='Alexa.SceneController',
        payload=payload,
    )


@HANDLERS.register(('Alexa.SceneController', 'Deactivate'))
@extract_entity
@asyncio.coroutine
def async_api_deactivate(hass, config, request, entity):
    """Process a deactivate request."""
    if entity.domain == group.DOMAIN:
        domain = ha.DOMAIN
    else:
        domain = entity.domain

    yield from hass.services.async_call(domain, SERVICE_TURN_OFF, {
        ATTR_ENTITY_ID: entity.entity_id
    }, blocking=False)

    payload = {
        'cause': {'type': _Cause.VOICE_INTERACTION},
        'timestamp': '%sZ' % (datetime.utcnow().isoformat(),)
    }

    return api_message(
        request,
        name='DeactivationStarted',
        namespace='Alexa.SceneController',
        payload=payload,
    )


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

    yield from hass.services.async_call(
        entity.domain, service, data, blocking=False)

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

    yield from hass.services.async_call(
        entity.domain, service, data, blocking=False)

    return api_message(request)


@HANDLERS.register(('Alexa.LockController', 'Lock'))
@extract_entity
@asyncio.coroutine
def async_api_lock(hass, config, request, entity):
    """Process a lock request."""
    yield from hass.services.async_call(entity.domain, SERVICE_LOCK, {
        ATTR_ENTITY_ID: entity.entity_id
    }, blocking=False)

    return api_message(request)


# Not supported by Alexa yet
@HANDLERS.register(('Alexa.LockController', 'Unlock'))
@extract_entity
@asyncio.coroutine
def async_api_unlock(hass, config, request, entity):
    """Process a unlock request."""
    yield from hass.services.async_call(entity.domain, SERVICE_UNLOCK, {
        ATTR_ENTITY_ID: entity.entity_id
    }, blocking=False)

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

    yield from hass.services.async_call(
        entity.domain, SERVICE_VOLUME_SET,
        data, blocking=False)

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

    yield from hass.services.async_call(
        entity.domain, media_player.SERVICE_VOLUME_SET,
        data, blocking=False)

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

    yield from hass.services.async_call(
        entity.domain, media_player.SERVICE_VOLUME_MUTE,
        data, blocking=False)

    return api_message(request)


@HANDLERS.register(('Alexa.PlaybackController', 'Play'))
@extract_entity
@asyncio.coroutine
def async_api_play(hass, config, request, entity):
    """Process a play request."""
    data = {
        ATTR_ENTITY_ID: entity.entity_id
    }

    yield from hass.services.async_call(
        entity.domain, SERVICE_MEDIA_PLAY,
        data, blocking=False)

    return api_message(request)


@HANDLERS.register(('Alexa.PlaybackController', 'Pause'))
@extract_entity
@asyncio.coroutine
def async_api_pause(hass, config, request, entity):
    """Process a pause request."""
    data = {
        ATTR_ENTITY_ID: entity.entity_id
    }

    yield from hass.services.async_call(
        entity.domain, SERVICE_MEDIA_PAUSE,
        data, blocking=False)

    return api_message(request)


@HANDLERS.register(('Alexa.PlaybackController', 'Stop'))
@extract_entity
@asyncio.coroutine
def async_api_stop(hass, config, request, entity):
    """Process a stop request."""
    data = {
        ATTR_ENTITY_ID: entity.entity_id
    }

    yield from hass.services.async_call(
        entity.domain, SERVICE_MEDIA_STOP,
        data, blocking=False)

    return api_message(request)


@HANDLERS.register(('Alexa.PlaybackController', 'Next'))
@extract_entity
@asyncio.coroutine
def async_api_next(hass, config, request, entity):
    """Process a next request."""
    data = {
        ATTR_ENTITY_ID: entity.entity_id
    }

    yield from hass.services.async_call(
        entity.domain, SERVICE_MEDIA_NEXT_TRACK,
        data, blocking=False)

    return api_message(request)


@HANDLERS.register(('Alexa.PlaybackController', 'Previous'))
@extract_entity
@asyncio.coroutine
def async_api_previous(hass, config, request, entity):
    """Process a previous request."""
    data = {
        ATTR_ENTITY_ID: entity.entity_id
    }

    yield from hass.services.async_call(
        entity.domain, SERVICE_MEDIA_PREVIOUS_TRACK,
        data, blocking=False)

    return api_message(request)


@HANDLERS.register(('Alexa', 'ReportState'))
@extract_entity
@asyncio.coroutine
def async_api_reportstate(hass, config, request, entity):
    """Process a ReportState request."""
    unit = entity.attributes[CONF_UNIT_OF_MEASUREMENT]
    temp_property = {
        'namespace': 'Alexa.TemperatureSensor',
        'name': 'temperature',
        'value': {
            'value': float(entity.state),
            'scale': API_TEMP_UNITS[unit],
        },
    }

    return api_message(
        request,
        name='StateReport',
        context={'properties': [temp_property]}
    )
