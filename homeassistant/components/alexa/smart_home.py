"""Support for alexa Smart Home Skill API."""
import asyncio
import logging
import math
from datetime import datetime
from uuid import uuid4

from homeassistant.components import (
    alert, automation, cover, climate, fan, group, input_boolean, light, lock,
    media_player, scene, script, switch, http, sensor)
import homeassistant.core as ha
import homeassistant.util.color as color_util
from homeassistant.util.temperature import convert as convert_temperature
from homeassistant.util.decorator import Registry
from homeassistant.const import (
    ATTR_ENTITY_ID, ATTR_SUPPORTED_FEATURES, ATTR_TEMPERATURE, CONF_NAME,
    SERVICE_LOCK, SERVICE_MEDIA_NEXT_TRACK, SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY, SERVICE_MEDIA_PREVIOUS_TRACK, SERVICE_MEDIA_STOP,
    SERVICE_SET_COVER_POSITION, SERVICE_TURN_OFF, SERVICE_TURN_ON,
    SERVICE_UNLOCK, SERVICE_VOLUME_SET, TEMP_FAHRENHEIT, TEMP_CELSIUS,
    CONF_UNIT_OF_MEASUREMENT, STATE_LOCKED, STATE_UNLOCKED, STATE_ON)

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

API_THERMOSTAT_MODES = {
    climate.STATE_HEAT: 'HEAT',
    climate.STATE_COOL: 'COOL',
    climate.STATE_AUTO: 'AUTO',
    climate.STATE_ECO: 'ECO',
    climate.STATE_IDLE: 'OFF',
    climate.STATE_FAN_ONLY: 'OFF',
    climate.STATE_DRY: 'OFF',
}

SMART_HOME_HTTP_ENDPOINT = '/api/alexa/smart_home'

CONF_DESCRIPTION = 'description'
CONF_DISPLAY_CATEGORIES = 'display_categories'

HANDLERS = Registry()
ENTITY_ADAPTERS = Registry()


class _DisplayCategory(object):
    """Possible display categories for Discovery response.

    https://developer.amazon.com/docs/device-apis/alexa-discovery.html#display-categories
    """

    # Describes a combination of devices set to a specific state, when the
    # state change must occur in a specific order. For example, a "watch
    # Netflix" scene might require the: 1. TV to be powered on & 2. Input set
    # to HDMI1. Applies to Scenes
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


class _UnsupportedInterface(Exception):
    """This entity does not support the requested Smart Home API interface."""


class _UnsupportedProperty(Exception):
    """This entity does not support the requested Smart Home API property."""


class _AlexaEntity(object):
    """An adaptation of an entity, expressed in Alexa's terms.

    The API handlers should manipulate entities only through this interface.
    """

    def __init__(self, config, entity):
        self.config = config
        self.entity = entity
        self.entity_conf = config.entity_config.get(entity.entity_id, {})

    def friendly_name(self):
        """Return the Alexa API friendly name."""
        return self.entity_conf.get(CONF_NAME, self.entity.name)

    def description(self):
        """Return the Alexa API description."""
        return self.entity_conf.get(CONF_DESCRIPTION, self.entity.entity_id)

    def entity_id(self):
        """Return the Alexa API entity id."""
        return self.entity.entity_id.replace('.', '#')

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

    def get_interface(self, capability):
        """Return the given _AlexaInterface.

        Raises _UnsupportedInterface.
        """
        pass

    def interfaces(self):
        """Return a list of supported interfaces.

        Used for discovery. The list should contain _AlexaInterface instances.
        If the list is empty, this entity will not be discovered.
        """
        raise NotImplementedError


class _AlexaInterface(object):
    def __init__(self, entity):
        self.entity = entity

    def name(self):
        """Return the Alexa API name of this interface."""
        raise NotImplementedError

    @staticmethod
    def properties_supported():
        """Return what properties this entity supports."""
        return []

    @staticmethod
    def properties_proactively_reported():
        """Return True if properties asynchronously reported."""
        return False

    @staticmethod
    def properties_retrievable():
        """Return True if properties can be retrieved."""
        return False

    @staticmethod
    def get_property(name):
        """Read and return a property.

        Return value should be a dict, or raise _UnsupportedProperty.

        Properties can also have a timeOfSample and uncertaintyInMilliseconds,
        but returning those metadata is not yet implemented.
        """
        raise _UnsupportedProperty(name)

    @staticmethod
    def supports_deactivation():
        """Applicable only to scenes."""
        return None

    def serialize_discovery(self):
        """Serialize according to the Discovery API."""
        result = {
            'type': 'AlexaInterface',
            'interface': self.name(),
            'version': '3',
            'properties': {
                'supported': self.properties_supported(),
                'proactivelyReported': self.properties_proactively_reported(),
                'retrievable': self.properties_retrievable(),
            },
        }

        # pylint: disable=assignment-from-none
        supports_deactivation = self.supports_deactivation()
        if supports_deactivation is not None:
            result['supportsDeactivation'] = supports_deactivation
        return result

    def serialize_properties(self):
        """Return properties serialized for an API response."""
        for prop in self.properties_supported():
            prop_name = prop['name']
            yield {
                'name': prop_name,
                'namespace': self.name(),
                'value': self.get_property(prop_name),
            }


class _AlexaPowerController(_AlexaInterface):
    def name(self):
        return 'Alexa.PowerController'

    def properties_supported(self):
        return [{'name': 'powerState'}]

    def properties_retrievable(self):
        return True

    def get_property(self, name):
        if name != 'powerState':
            raise _UnsupportedProperty(name)

        if self.entity.state == STATE_ON:
            return 'ON'
        return 'OFF'


class _AlexaLockController(_AlexaInterface):
    def name(self):
        return 'Alexa.LockController'

    def properties_supported(self):
        return [{'name': 'lockState'}]

    def properties_retrievable(self):
        return True

    def get_property(self, name):
        if name != 'lockState':
            raise _UnsupportedProperty(name)

        if self.entity.state == STATE_LOCKED:
            return 'LOCKED'
        elif self.entity.state == STATE_UNLOCKED:
            return 'UNLOCKED'
        return 'JAMMED'


class _AlexaSceneController(_AlexaInterface):
    def __init__(self, entity, supports_deactivation):
        _AlexaInterface.__init__(self, entity)
        self.supports_deactivation = lambda: supports_deactivation

    def name(self):
        return 'Alexa.SceneController'


class _AlexaBrightnessController(_AlexaInterface):
    def name(self):
        return 'Alexa.BrightnessController'

    def properties_supported(self):
        return [{'name': 'brightness'}]

    def properties_retrievable(self):
        return True

    def get_property(self, name):
        if name != 'brightness':
            raise _UnsupportedProperty(name)
        if 'brightness' in self.entity.attributes:
            return round(self.entity.attributes['brightness'] / 255.0 * 100)
        return 0


class _AlexaColorController(_AlexaInterface):
    def name(self):
        return 'Alexa.ColorController'


class _AlexaColorTemperatureController(_AlexaInterface):
    def name(self):
        return 'Alexa.ColorTemperatureController'


class _AlexaPercentageController(_AlexaInterface):
    def name(self):
        return 'Alexa.PercentageController'


class _AlexaSpeaker(_AlexaInterface):
    def name(self):
        return 'Alexa.Speaker'


class _AlexaStepSpeaker(_AlexaInterface):
    def name(self):
        return 'Alexa.StepSpeaker'


class _AlexaPlaybackController(_AlexaInterface):
    def name(self):
        return 'Alexa.PlaybackController'


class _AlexaInputController(_AlexaInterface):
    def name(self):
        return 'Alexa.InputController'


class _AlexaTemperatureSensor(_AlexaInterface):
    def name(self):
        return 'Alexa.TemperatureSensor'

    def properties_supported(self):
        return [{'name': 'temperature'}]

    def properties_retrievable(self):
        return True

    def get_property(self, name):
        if name != 'temperature':
            raise _UnsupportedProperty(name)

        unit = self.entity.attributes[CONF_UNIT_OF_MEASUREMENT]
        temp = self.entity.state
        if self.entity.domain == climate.DOMAIN:
            temp = self.entity.attributes.get(
                climate.ATTR_CURRENT_TEMPERATURE)
        return {
            'value': float(temp),
            'scale': API_TEMP_UNITS[unit],
        }


class _AlexaThermostatController(_AlexaInterface):
    def name(self):
        return 'Alexa.ThermostatController'

    def properties_supported(self):
        properties = []
        supported = self.entity.attributes.get(ATTR_SUPPORTED_FEATURES, 0)
        if supported & climate.SUPPORT_TARGET_TEMPERATURE:
            properties.append({'name': 'targetSetpoint'})
        if supported & climate.SUPPORT_TARGET_TEMPERATURE_LOW:
            properties.append({'name': 'lowerSetpoint'})
        if supported & climate.SUPPORT_TARGET_TEMPERATURE_HIGH:
            properties.append({'name': 'upperSetpoint'})
        if supported & climate.SUPPORT_OPERATION_MODE:
            properties.append({'name': 'thermostatMode'})
        return properties

    def properties_retrievable(self):
        return True

    def get_property(self, name):
        if name == 'thermostatMode':
            ha_mode = self.entity.attributes.get(climate.ATTR_OPERATION_MODE)
            mode = API_THERMOSTAT_MODES.get(ha_mode)
            if mode is None:
                _LOGGER.error("%s (%s) has unsupported %s value '%s'",
                              self.entity.entity_id, type(self.entity),
                              climate.ATTR_OPERATION_MODE, ha_mode)
                raise _UnsupportedProperty(name)
            return mode

        unit = self.entity.attributes[CONF_UNIT_OF_MEASUREMENT]
        temp = None
        if name == 'targetSetpoint':
            temp = self.entity.attributes.get(ATTR_TEMPERATURE)
        elif name == 'lowerSetpoint':
            temp = self.entity.attributes.get(climate.ATTR_TARGET_TEMP_LOW)
        elif name == 'upperSetpoint':
            temp = self.entity.attributes.get(climate.ATTR_TARGET_TEMP_HIGH)
        if temp is None:
            raise _UnsupportedProperty(name)

        return {
            'value': float(temp),
            'scale': API_TEMP_UNITS[unit],
        }


@ENTITY_ADAPTERS.register(alert.DOMAIN)
@ENTITY_ADAPTERS.register(automation.DOMAIN)
@ENTITY_ADAPTERS.register(group.DOMAIN)
@ENTITY_ADAPTERS.register(input_boolean.DOMAIN)
class _GenericCapabilities(_AlexaEntity):
    """A generic, on/off device.

    The choice of last resort.
    """

    def default_display_categories(self):
        return [_DisplayCategory.OTHER]

    def interfaces(self):
        return [_AlexaPowerController(self.entity)]


@ENTITY_ADAPTERS.register(switch.DOMAIN)
class _SwitchCapabilities(_AlexaEntity):
    def default_display_categories(self):
        return [_DisplayCategory.SWITCH]

    def interfaces(self):
        return [_AlexaPowerController(self.entity)]


@ENTITY_ADAPTERS.register(climate.DOMAIN)
class _ClimateCapabilities(_AlexaEntity):
    def default_display_categories(self):
        return [_DisplayCategory.THERMOSTAT]

    def interfaces(self):
        yield _AlexaThermostatController(self.entity)
        yield _AlexaTemperatureSensor(self.entity)


@ENTITY_ADAPTERS.register(cover.DOMAIN)
class _CoverCapabilities(_AlexaEntity):
    def default_display_categories(self):
        return [_DisplayCategory.DOOR]

    def interfaces(self):
        yield _AlexaPowerController(self.entity)
        supported = self.entity.attributes.get(ATTR_SUPPORTED_FEATURES, 0)
        if supported & cover.SUPPORT_SET_POSITION:
            yield _AlexaPercentageController(self.entity)


@ENTITY_ADAPTERS.register(light.DOMAIN)
class _LightCapabilities(_AlexaEntity):
    def default_display_categories(self):
        return [_DisplayCategory.LIGHT]

    def interfaces(self):
        yield _AlexaPowerController(self.entity)

        supported = self.entity.attributes.get(ATTR_SUPPORTED_FEATURES, 0)
        if supported & light.SUPPORT_BRIGHTNESS:
            yield _AlexaBrightnessController(self.entity)
        if supported & light.SUPPORT_COLOR:
            yield _AlexaColorController(self.entity)
        if supported & light.SUPPORT_COLOR_TEMP:
            yield _AlexaColorTemperatureController(self.entity)


@ENTITY_ADAPTERS.register(fan.DOMAIN)
class _FanCapabilities(_AlexaEntity):
    def default_display_categories(self):
        return [_DisplayCategory.OTHER]

    def interfaces(self):
        yield _AlexaPowerController(self.entity)
        supported = self.entity.attributes.get(ATTR_SUPPORTED_FEATURES, 0)
        if supported & fan.SUPPORT_SET_SPEED:
            yield _AlexaPercentageController(self.entity)


@ENTITY_ADAPTERS.register(lock.DOMAIN)
class _LockCapabilities(_AlexaEntity):
    def default_display_categories(self):
        return [_DisplayCategory.SMARTLOCK]

    def interfaces(self):
        return [_AlexaLockController(self.entity)]


@ENTITY_ADAPTERS.register(media_player.DOMAIN)
class _MediaPlayerCapabilities(_AlexaEntity):
    def default_display_categories(self):
        return [_DisplayCategory.TV]

    def interfaces(self):
        yield _AlexaPowerController(self.entity)

        supported = self.entity.attributes.get(ATTR_SUPPORTED_FEATURES, 0)
        if supported & media_player.SUPPORT_VOLUME_SET:
            yield _AlexaSpeaker(self.entity)

        step_volume_features = (media_player.SUPPORT_VOLUME_MUTE |
                                media_player.SUPPORT_VOLUME_STEP)
        if supported & step_volume_features:
            yield _AlexaStepSpeaker(self.entity)

        playback_features = (media_player.SUPPORT_PLAY |
                             media_player.SUPPORT_PAUSE |
                             media_player.SUPPORT_STOP |
                             media_player.SUPPORT_NEXT_TRACK |
                             media_player.SUPPORT_PREVIOUS_TRACK)
        if supported & playback_features:
            yield _AlexaPlaybackController(self.entity)

        if supported & media_player.SUPPORT_SELECT_SOURCE:
            yield _AlexaInputController(self.entity)


@ENTITY_ADAPTERS.register(scene.DOMAIN)
class _SceneCapabilities(_AlexaEntity):
    def description(self):
        # Required description as per Amazon Scene docs
        scene_fmt = '{} (Scene connected via Home Assistant)'
        return scene_fmt.format(_AlexaEntity.description(self))

    def default_display_categories(self):
        return [_DisplayCategory.SCENE_TRIGGER]

    def interfaces(self):
        return [_AlexaSceneController(self.entity,
                                      supports_deactivation=False)]


@ENTITY_ADAPTERS.register(script.DOMAIN)
class _ScriptCapabilities(_AlexaEntity):
    def default_display_categories(self):
        return [_DisplayCategory.ACTIVITY_TRIGGER]

    def interfaces(self):
        can_cancel = bool(self.entity.attributes.get('can_cancel'))
        return [_AlexaSceneController(self.entity,
                                      supports_deactivation=can_cancel)]


@ENTITY_ADAPTERS.register(sensor.DOMAIN)
class _SensorCapabilities(_AlexaEntity):
    def default_display_categories(self):
        # although there are other kinds of sensors, all but temperature
        # sensors are currently ignored.
        return [_DisplayCategory.TEMPERATURE_SENSOR]

    def interfaces(self):
        attrs = self.entity.attributes
        if attrs.get(CONF_UNIT_OF_MEASUREMENT) in (
                TEMP_FAHRENHEIT,
                TEMP_CELSIUS,
        ):
            yield _AlexaTemperatureSensor(self.entity)


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

    # If a correlation token exists, add it to header / Need by Async requests
    token = request[API_HEADER].get('correlationToken')
    if token:
        response[API_EVENT][API_HEADER]['correlationToken'] = token

    # Extend event with endpoint object / Need by Async requests
    if API_ENDPOINT in request:
        response[API_EVENT][API_ENDPOINT] = request[API_ENDPOINT].copy()

    if context is not None:
        response[API_CONTEXT] = context

    return response


def api_error(request,
              namespace='Alexa',
              error_type='INTERNAL_ERROR',
              error_message="",
              payload=None):
    """Create a API formatted error response.

    Async friendly.
    """
    payload = payload or {}
    payload['type'] = error_type
    payload['message'] = error_message

    _LOGGER.info("Request %s/%s error %s: %s",
                 request[API_HEADER]['namespace'],
                 request[API_HEADER]['name'],
                 error_type, error_message)

    return api_message(
        request, name='ErrorResponse', namespace=namespace, payload=payload)


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

        if entity.domain not in ENTITY_ADAPTERS:
            continue
        alexa_entity = ENTITY_ADAPTERS[entity.domain](config, entity)

        endpoint = {
            'displayCategories': alexa_entity.display_categories(),
            'additionalApplianceDetails': {},
            'endpointId': alexa_entity.entity_id(),
            'friendlyName': alexa_entity.friendly_name(),
            'description': alexa_entity.description(),
            'manufacturerName': 'Home Assistant',
        }

        endpoint['capabilities'] = [
            i.serialize_discovery() for i in alexa_entity.interfaces()]

        if not endpoint['capabilities']:
            _LOGGER.debug("Not exposing %s because it has no capabilities",
                          entity.entity_id)
            continue
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
    if entity.domain == group.DOMAIN:
        domain = ha.DOMAIN

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
    """Process an adjust brightness request."""
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
    rgb = color_util.color_hsb_to_RGB(
        float(request[API_PAYLOAD]['color']['hue']),
        float(request[API_PAYLOAD]['color']['saturation']),
        float(request[API_PAYLOAD]['color']['brightness'])
    )

    yield from hass.services.async_call(entity.domain, SERVICE_TURN_ON, {
        ATTR_ENTITY_ID: entity.entity_id,
        light.ATTR_RGB_COLOR: rgb,
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
    """Process an adjust percentage request."""
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

    # Alexa expects a lockState in the response, we don't know the actual
    # lockState at this point but assume it is locked. It is reported
    # correctly later when ReportState is called. The alt. to this approach
    # is to implement DeferredResponse
    properties = [{
        'name': 'lockState',
        'namespace': 'Alexa.LockController',
        'value': 'LOCKED'
    }]
    return api_message(request, context={'properties': properties})


# Not supported by Alexa yet
@HANDLERS.register(('Alexa.LockController', 'Unlock'))
@extract_entity
@asyncio.coroutine
def async_api_unlock(hass, config, request, entity):
    """Process an unlock request."""
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


@HANDLERS.register(('Alexa.InputController', 'SelectInput'))
@extract_entity
@asyncio.coroutine
def async_api_select_input(hass, config, request, entity):
    """Process a set input request."""
    media_input = request[API_PAYLOAD]['input']

    # attempt to map the ALL UPPERCASE payload name to a source
    source_list = entity.attributes[media_player.ATTR_INPUT_SOURCE_LIST] or []
    for source in source_list:
        # response will always be space separated, so format the source in the
        # most likely way to find a match
        formatted_source = source.lower().replace('-', ' ').replace('_', ' ')
        if formatted_source in media_input.lower():
            media_input = source
            break
    else:
        msg = 'failed to map input {} to a media source on {}'.format(
            media_input, entity.entity_id)
        return api_error(
            request, error_type='INVALID_VALUE', error_message=msg)

    data = {
        ATTR_ENTITY_ID: entity.entity_id,
        media_player.ATTR_INPUT_SOURCE: media_input,
    }

    yield from hass.services.async_call(
        entity.domain, media_player.SERVICE_SELECT_SOURCE,
        data, blocking=False)

    return api_message(request)


@HANDLERS.register(('Alexa.Speaker', 'AdjustVolume'))
@extract_entity
@asyncio.coroutine
def async_api_adjust_volume(hass, config, request, entity):
    """Process an adjust volume request."""
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


@HANDLERS.register(('Alexa.StepSpeaker', 'AdjustVolume'))
@extract_entity
@asyncio.coroutine
def async_api_adjust_volume_step(hass, config, request, entity):
    """Process an adjust volume step request."""
    # media_player volume up/down service does not support specifying steps
    # each component handles it differently e.g. via config.
    # For now we use the volumeSteps returned to figure out if we
    # should step up/down
    volume_step = request[API_PAYLOAD]['volumeSteps']

    data = {
        ATTR_ENTITY_ID: entity.entity_id,
    }

    if volume_step > 0:
        yield from hass.services.async_call(
            entity.domain, media_player.SERVICE_VOLUME_UP,
            data, blocking=False)
    elif volume_step < 0:
        yield from hass.services.async_call(
            entity.domain, media_player.SERVICE_VOLUME_DOWN,
            data, blocking=False)

    return api_message(request)


@HANDLERS.register(('Alexa.StepSpeaker', 'SetMute'))
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


def api_error_temp_range(request, temp, min_temp, max_temp, unit):
    """Create temperature value out of range API error response.

    Async friendly.
    """
    temp_range = {
        'minimumValue': {
            'value': min_temp,
            'scale': API_TEMP_UNITS[unit],
        },
        'maximumValue': {
            'value': max_temp,
            'scale': API_TEMP_UNITS[unit],
        },
    }

    msg = 'The requested temperature {} is out of range'.format(temp)
    return api_error(
        request,
        error_type='TEMPERATURE_VALUE_OUT_OF_RANGE',
        error_message=msg,
        payload={'validRange': temp_range},
    )


def temperature_from_object(temp_obj, to_unit, interval=False):
    """Get temperature from Temperature object in requested unit."""
    from_unit = TEMP_CELSIUS
    temp = float(temp_obj['value'])

    if temp_obj['scale'] == 'FAHRENHEIT':
        from_unit = TEMP_FAHRENHEIT
    elif temp_obj['scale'] == 'KELVIN':
        # convert to Celsius if absolute temperature
        if not interval:
            temp -= 273.15

    return convert_temperature(temp, from_unit, to_unit, interval)


@HANDLERS.register(('Alexa.ThermostatController', 'SetTargetTemperature'))
@extract_entity
async def async_api_set_target_temp(hass, config, request, entity):
    """Process a set target temperature request."""
    unit = entity.attributes[CONF_UNIT_OF_MEASUREMENT]
    min_temp = entity.attributes.get(climate.ATTR_MIN_TEMP)
    max_temp = entity.attributes.get(climate.ATTR_MAX_TEMP)

    data = {
        ATTR_ENTITY_ID: entity.entity_id
    }

    payload = request[API_PAYLOAD]
    if 'targetSetpoint' in payload:
        temp = temperature_from_object(
            payload['targetSetpoint'], unit)
        if temp < min_temp or temp > max_temp:
            return api_error_temp_range(
                request, temp, min_temp, max_temp, unit)
        data[ATTR_TEMPERATURE] = temp
    if 'lowerSetpoint' in payload:
        temp_low = temperature_from_object(
            payload['lowerSetpoint'], unit)
        if temp_low < min_temp or temp_low > max_temp:
            return api_error_temp_range(
                request, temp_low, min_temp, max_temp, unit)
        data[climate.ATTR_TARGET_TEMP_LOW] = temp_low
    if 'upperSetpoint' in payload:
        temp_high = temperature_from_object(
            payload['upperSetpoint'], unit)
        if temp_high < min_temp or temp_high > max_temp:
            return api_error_temp_range(
                request, temp_high, min_temp, max_temp, unit)
        data[climate.ATTR_TARGET_TEMP_HIGH] = temp_high

    await hass.services.async_call(
        entity.domain, climate.SERVICE_SET_TEMPERATURE, data, blocking=False)

    return api_message(request)


@HANDLERS.register(('Alexa.ThermostatController', 'AdjustTargetTemperature'))
@extract_entity
async def async_api_adjust_target_temp(hass, config, request, entity):
    """Process an adjust target temperature request."""
    unit = entity.attributes[CONF_UNIT_OF_MEASUREMENT]
    min_temp = entity.attributes.get(climate.ATTR_MIN_TEMP)
    max_temp = entity.attributes.get(climate.ATTR_MAX_TEMP)

    temp_delta = temperature_from_object(
        request[API_PAYLOAD]['targetSetpointDelta'], unit, interval=True)
    target_temp = float(entity.attributes.get(ATTR_TEMPERATURE)) + temp_delta

    if target_temp < min_temp or target_temp > max_temp:
        return api_error_temp_range(
            request, target_temp, min_temp, max_temp, unit)

    data = {
        ATTR_ENTITY_ID: entity.entity_id,
        ATTR_TEMPERATURE: target_temp,
    }

    await hass.services.async_call(
        entity.domain, climate.SERVICE_SET_TEMPERATURE, data, blocking=False)

    return api_message(request)


@HANDLERS.register(('Alexa.ThermostatController', 'SetThermostatMode'))
@extract_entity
async def async_api_set_thermostat_mode(hass, config, request, entity):
    """Process a set thermostat mode request."""
    mode = request[API_PAYLOAD]['thermostatMode']

    operation_list = entity.attributes.get(climate.ATTR_OPERATION_LIST)
    # Work around a pylint false positive due to
    #  https://github.com/PyCQA/pylint/issues/1830
    # pylint: disable=stop-iteration-return
    ha_mode = next(
        (k for k, v in API_THERMOSTAT_MODES.items() if v == mode),
        None
    )
    if ha_mode not in operation_list:
        msg = 'The requested thermostat mode {} is not supported'.format(mode)
        return api_error(
            request,
            namespace='Alexa.ThermostatController',
            error_type='UNSUPPORTED_THERMOSTAT_MODE',
            error_message=msg
        )

    data = {
        ATTR_ENTITY_ID: entity.entity_id,
        climate.ATTR_OPERATION_MODE: ha_mode,
    }

    await hass.services.async_call(
        entity.domain, climate.SERVICE_SET_OPERATION_MODE, data,
        blocking=False)

    return api_message(request)


@HANDLERS.register(('Alexa', 'ReportState'))
@extract_entity
@asyncio.coroutine
def async_api_reportstate(hass, config, request, entity):
    """Process a ReportState request."""
    alexa_entity = ENTITY_ADAPTERS[entity.domain](config, entity)
    properties = []
    for interface in alexa_entity.interfaces():
        properties.extend(interface.serialize_properties())

    return api_message(
        request,
        name='StateReport',
        context={'properties': properties}
    )
