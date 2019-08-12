"""Support for alexa Smart Home Skill API."""
import asyncio
import json
import logging
import math
from collections import OrderedDict
from datetime import datetime
from uuid import uuid4

import aiohttp
import async_timeout

import homeassistant.core as ha
import homeassistant.util.color as color_util
from homeassistant.components import (
    alert, automation, binary_sensor, cover, fan, group, http,
    input_boolean, light, lock, media_player, scene, script, sensor, switch)
from homeassistant.components.climate import const as climate
from homeassistant.const import (
    ATTR_DEVICE_CLASS, ATTR_ENTITY_ID, ATTR_SUPPORTED_FEATURES,
    ATTR_TEMPERATURE, ATTR_UNIT_OF_MEASUREMENT, CLOUD_NEVER_EXPOSED_ENTITIES,
    CONF_NAME, SERVICE_LOCK, SERVICE_MEDIA_NEXT_TRACK, SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY, SERVICE_MEDIA_PREVIOUS_TRACK, SERVICE_MEDIA_STOP,
    SERVICE_SET_COVER_POSITION, SERVICE_TURN_OFF, SERVICE_TURN_ON,
    SERVICE_UNLOCK, SERVICE_VOLUME_DOWN, SERVICE_VOLUME_UP, SERVICE_VOLUME_SET,
    SERVICE_VOLUME_MUTE, STATE_LOCKED, STATE_ON, STATE_OFF, STATE_UNAVAILABLE,
    STATE_UNLOCKED, TEMP_CELSIUS, TEMP_FAHRENHEIT, MATCH_ALL)
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.event import async_track_state_change
from homeassistant.util.decorator import Registry
from homeassistant.util.temperature import convert as convert_temperature

from .auth import Auth
from .const import CONF_CLIENT_ID, CONF_CLIENT_SECRET, CONF_ENDPOINT, \
    CONF_ENTITY_CONFIG, CONF_FILTER, DATE_FORMAT, DEFAULT_TIMEOUT

_LOGGER = logging.getLogger(__name__)

API_DIRECTIVE = 'directive'
API_ENDPOINT = 'endpoint'
API_EVENT = 'event'
API_CONTEXT = 'context'
API_HEADER = 'header'
API_PAYLOAD = 'payload'
API_SCOPE = 'scope'
API_CHANGE = 'change'

API_TEMP_UNITS = {
    TEMP_FAHRENHEIT: 'FAHRENHEIT',
    TEMP_CELSIUS: 'CELSIUS',
}

# Needs to be ordered dict for `async_api_set_thermostat_mode` which does a
# reverse mapping of this dict and we want to map the first occurrance of OFF
# back to HA state.
API_THERMOSTAT_MODES = OrderedDict([
    (climate.STATE_HEAT, 'HEAT'),
    (climate.STATE_COOL, 'COOL'),
    (climate.STATE_AUTO, 'AUTO'),
    (climate.STATE_ECO, 'ECO'),
    (climate.STATE_MANUAL, 'AUTO'),
    (STATE_OFF, 'OFF'),
    (climate.STATE_IDLE, 'OFF'),
    (climate.STATE_FAN_ONLY, 'OFF'),
    (climate.STATE_DRY, 'OFF'),
])

PERCENTAGE_FAN_MAP = {
    fan.SPEED_LOW: 33,
    fan.SPEED_MEDIUM: 66,
    fan.SPEED_HIGH: 100,
}

SMART_HOME_HTTP_ENDPOINT = '/api/alexa/smart_home'

CONF_DESCRIPTION = 'description'
CONF_DISPLAY_CATEGORIES = 'display_categories'

HANDLERS = Registry()
ENTITY_ADAPTERS = Registry()
EVENT_ALEXA_SMART_HOME = 'alexa_smart_home'

AUTH_KEY = "alexa.smart_home.auth"


class _DisplayCategory:
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

    # Indicates an endpoint that detects and reports contact.
    CONTACT_SENSOR = "CONTACT_SENSOR"

    # Indicates a door.
    DOOR = "DOOR"

    # Indicates light sources or fixtures.
    LIGHT = "LIGHT"

    # Indicates an endpoint that detects and reports motion.
    MOTION_SENSOR = "MOTION_SENSOR"

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


class _AlexaError(Exception):
    """Base class for errors that can be serialized by the Alexa API.

    A handler can raise subclasses of this to return an error to the request.
    """

    namespace = None
    error_type = None

    def __init__(self, error_message, payload=None):
        Exception.__init__(self)
        self.error_message = error_message
        self.payload = None


class _AlexaInvalidEndpointError(_AlexaError):
    """The endpoint in the request does not exist."""

    namespace = 'Alexa'
    error_type = 'NO_SUCH_ENDPOINT'

    def __init__(self, endpoint_id):
        msg = 'The endpoint {} does not exist'.format(endpoint_id)
        _AlexaError.__init__(self, msg)
        self.endpoint_id = endpoint_id


class _AlexaInvalidValueError(_AlexaError):
    namespace = 'Alexa'
    error_type = 'INVALID_VALUE'


class _AlexaUnsupportedThermostatModeError(_AlexaError):
    namespace = 'Alexa.ThermostatController'
    error_type = 'UNSUPPORTED_THERMOSTAT_MODE'


class _AlexaTempRangeError(_AlexaError):
    namespace = 'Alexa'
    error_type = 'TEMPERATURE_VALUE_OUT_OF_RANGE'

    def __init__(self, hass, temp, min_temp, max_temp):
        unit = hass.config.units.temperature_unit
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
        payload = {'validRange': temp_range}
        msg = 'The requested temperature {} is out of range'.format(temp)

        _AlexaError.__init__(self, msg, payload)


class _AlexaBridgeUnreachableError(_AlexaError):
    namespace = 'Alexa'
    error_type = 'BRIDGE_UNREACHABLE'


class _AlexaEntity:
    """An adaptation of an entity, expressed in Alexa's terms.

    The API handlers should manipulate entities only through this interface.
    """

    def __init__(self, hass, config, entity):
        self.hass = hass
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

    def serialize_properties(self):
        """Yield each supported property in API format."""
        for interface in self.interfaces():
            for prop in interface.serialize_properties():
                yield prop


class _AlexaInterface:
    """Base class for Alexa capability interfaces.

    The Smart Home Skills API defines a number of "capability interfaces",
    roughly analogous to domains in Home Assistant. The supported interfaces
    describe what actions can be performed on a particular device.

    https://developer.amazon.com/docs/device-apis/message-guide.html
    """

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
            # pylint: disable=assignment-from-no-return
            prop_value = self.get_property(prop_name)
            if prop_value is not None:
                yield {
                    'name': prop_name,
                    'namespace': self.name(),
                    'value': prop_value,
                    'timeOfSample': datetime.now().strftime(DATE_FORMAT),
                    'uncertaintyInMilliseconds': 0
                }


class _AlexaEndpointHealth(_AlexaInterface):
    """Implements Alexa.EndpointHealth.

    https://developer.amazon.com/docs/smarthome/state-reporting-for-a-smart-home-skill.html#report-state-when-alexa-requests-it
    """

    def __init__(self, hass, entity):
        super().__init__(entity)
        self.hass = hass

    def name(self):
        return 'Alexa.EndpointHealth'

    def properties_supported(self):
        return [{'name': 'connectivity'}]

    def properties_proactively_reported(self):
        return False

    def properties_retrievable(self):
        return True

    def get_property(self, name):
        if name != 'connectivity':
            raise _UnsupportedProperty(name)

        if self.entity.state == STATE_UNAVAILABLE:
            return {'value': 'UNREACHABLE'}
        return {'value': 'OK'}


class _AlexaPowerController(_AlexaInterface):
    """Implements Alexa.PowerController.

    https://developer.amazon.com/docs/device-apis/alexa-powercontroller.html
    """

    def name(self):
        return 'Alexa.PowerController'

    def properties_supported(self):
        return [{'name': 'powerState'}]

    def properties_proactively_reported(self):
        return True

    def properties_retrievable(self):
        return True

    def get_property(self, name):
        if name != 'powerState':
            raise _UnsupportedProperty(name)

        if self.entity.state == STATE_OFF:
            return 'OFF'
        return 'ON'


class _AlexaLockController(_AlexaInterface):
    """Implements Alexa.LockController.

    https://developer.amazon.com/docs/device-apis/alexa-lockcontroller.html
    """

    def name(self):
        return 'Alexa.LockController'

    def properties_supported(self):
        return [{'name': 'lockState'}]

    def properties_retrievable(self):
        return True

    def properties_proactively_reported(self):
        return True

    def get_property(self, name):
        if name != 'lockState':
            raise _UnsupportedProperty(name)

        if self.entity.state == STATE_LOCKED:
            return 'LOCKED'
        if self.entity.state == STATE_UNLOCKED:
            return 'UNLOCKED'
        return 'JAMMED'


class _AlexaSceneController(_AlexaInterface):
    """Implements Alexa.SceneController.

    https://developer.amazon.com/docs/device-apis/alexa-scenecontroller.html
    """

    def __init__(self, entity, supports_deactivation):
        _AlexaInterface.__init__(self, entity)
        self.supports_deactivation = lambda: supports_deactivation

    def name(self):
        return 'Alexa.SceneController'


class _AlexaBrightnessController(_AlexaInterface):
    """Implements Alexa.BrightnessController.

    https://developer.amazon.com/docs/device-apis/alexa-brightnesscontroller.html
    """

    def name(self):
        return 'Alexa.BrightnessController'

    def properties_supported(self):
        return [{'name': 'brightness'}]

    def properties_proactively_reported(self):
        return True

    def properties_retrievable(self):
        return True

    def get_property(self, name):
        if name != 'brightness':
            raise _UnsupportedProperty(name)
        if 'brightness' in self.entity.attributes:
            return round(self.entity.attributes['brightness'] / 255.0 * 100)
        return 0


class _AlexaColorController(_AlexaInterface):
    """Implements Alexa.ColorController.

    https://developer.amazon.com/docs/device-apis/alexa-colorcontroller.html
    """

    def name(self):
        return 'Alexa.ColorController'

    def properties_supported(self):
        return [{'name': 'color'}]

    def properties_retrievable(self):
        return True

    def get_property(self, name):
        if name != 'color':
            raise _UnsupportedProperty(name)

        hue, saturation = self.entity.attributes.get(
            light.ATTR_HS_COLOR, (0, 0))

        return {
            'hue': hue,
            'saturation': saturation / 100.0,
            'brightness': self.entity.attributes.get(
                light.ATTR_BRIGHTNESS, 0) / 255.0,
        }


class _AlexaColorTemperatureController(_AlexaInterface):
    """Implements Alexa.ColorTemperatureController.

    https://developer.amazon.com/docs/device-apis/alexa-colortemperaturecontroller.html
    """

    def name(self):
        return 'Alexa.ColorTemperatureController'

    def properties_supported(self):
        return [{'name': 'colorTemperatureInKelvin'}]

    def properties_retrievable(self):
        return True

    def get_property(self, name):
        if name != 'colorTemperatureInKelvin':
            raise _UnsupportedProperty(name)
        if 'color_temp' in self.entity.attributes:
            return color_util.color_temperature_mired_to_kelvin(
                self.entity.attributes['color_temp'])
        return 0


class _AlexaPercentageController(_AlexaInterface):
    """Implements Alexa.PercentageController.

    https://developer.amazon.com/docs/device-apis/alexa-percentagecontroller.html
    """

    def name(self):
        return 'Alexa.PercentageController'

    def properties_supported(self):
        return [{'name': 'percentage'}]

    def properties_retrievable(self):
        return True

    def get_property(self, name):
        if name != 'percentage':
            raise _UnsupportedProperty(name)

        if self.entity.domain == fan.DOMAIN:
            speed = self.entity.attributes.get(fan.ATTR_SPEED)

            return PERCENTAGE_FAN_MAP.get(speed, 0)

        if self.entity.domain == cover.DOMAIN:
            return self.entity.attributes.get(cover.ATTR_CURRENT_POSITION, 0)

        return 0


class _AlexaSpeaker(_AlexaInterface):
    """Implements Alexa.Speaker.

    https://developer.amazon.com/docs/device-apis/alexa-speaker.html
    """

    def name(self):
        return 'Alexa.Speaker'


class _AlexaStepSpeaker(_AlexaInterface):
    """Implements Alexa.StepSpeaker.

    https://developer.amazon.com/docs/device-apis/alexa-stepspeaker.html
    """

    def name(self):
        return 'Alexa.StepSpeaker'


class _AlexaPlaybackController(_AlexaInterface):
    """Implements Alexa.PlaybackController.

    https://developer.amazon.com/docs/device-apis/alexa-playbackcontroller.html
    """

    def name(self):
        return 'Alexa.PlaybackController'


class _AlexaInputController(_AlexaInterface):
    """Implements Alexa.InputController.

    https://developer.amazon.com/docs/device-apis/alexa-inputcontroller.html
    """

    def name(self):
        return 'Alexa.InputController'


class _AlexaTemperatureSensor(_AlexaInterface):
    """Implements Alexa.TemperatureSensor.

    https://developer.amazon.com/docs/device-apis/alexa-temperaturesensor.html
    """

    def __init__(self, hass, entity):
        _AlexaInterface.__init__(self, entity)
        self.hass = hass

    def name(self):
        return 'Alexa.TemperatureSensor'

    def properties_supported(self):
        return [{'name': 'temperature'}]

    def properties_proactively_reported(self):
        return True

    def properties_retrievable(self):
        return True

    def get_property(self, name):
        if name != 'temperature':
            raise _UnsupportedProperty(name)

        unit = self.entity.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        temp = self.entity.state
        if self.entity.domain == climate.DOMAIN:
            unit = self.hass.config.units.temperature_unit
            temp = self.entity.attributes.get(
                climate.ATTR_CURRENT_TEMPERATURE)
        return {
            'value': float(temp),
            'scale': API_TEMP_UNITS[unit],
        }


class _AlexaContactSensor(_AlexaInterface):
    """Implements Alexa.ContactSensor.

    The Alexa.ContactSensor interface describes the properties and events used
    to report the state of an endpoint that detects contact between two
    surfaces. For example, a contact sensor can report whether a door or window
    is open.

    https://developer.amazon.com/docs/device-apis/alexa-contactsensor.html
    """

    def __init__(self, hass, entity):
        _AlexaInterface.__init__(self, entity)
        self.hass = hass

    def name(self):
        return 'Alexa.ContactSensor'

    def properties_supported(self):
        return [{'name': 'detectionState'}]

    def properties_proactively_reported(self):
        return True

    def properties_retrievable(self):
        return True

    def get_property(self, name):
        if name != 'detectionState':
            raise _UnsupportedProperty(name)

        if self.entity.state == STATE_ON:
            return 'DETECTED'
        return 'NOT_DETECTED'


class _AlexaMotionSensor(_AlexaInterface):
    def __init__(self, hass, entity):
        _AlexaInterface.__init__(self, entity)
        self.hass = hass

    def name(self):
        return 'Alexa.MotionSensor'

    def properties_supported(self):
        return [{'name': 'detectionState'}]

    def properties_proactively_reported(self):
        return True

    def properties_retrievable(self):
        return True

    def get_property(self, name):
        if name != 'detectionState':
            raise _UnsupportedProperty(name)

        if self.entity.state == STATE_ON:
            return 'DETECTED'
        return 'NOT_DETECTED'


class _AlexaThermostatController(_AlexaInterface):
    """Implements Alexa.ThermostatController.

    https://developer.amazon.com/docs/device-apis/alexa-thermostatcontroller.html
    """

    def __init__(self, hass, entity):
        _AlexaInterface.__init__(self, entity)
        self.hass = hass

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

    def properties_proactively_reported(self):
        return True

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

        unit = self.hass.config.units.temperature_unit
        if name == 'targetSetpoint':
            temp = self.entity.attributes.get(ATTR_TEMPERATURE)
        elif name == 'lowerSetpoint':
            temp = self.entity.attributes.get(climate.ATTR_TARGET_TEMP_LOW)
        elif name == 'upperSetpoint':
            temp = self.entity.attributes.get(climate.ATTR_TARGET_TEMP_HIGH)
        else:
            raise _UnsupportedProperty(name)

        if temp is None:
            return None

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
        return [_AlexaPowerController(self.entity),
                _AlexaEndpointHealth(self.hass, self.entity)]


@ENTITY_ADAPTERS.register(switch.DOMAIN)
class _SwitchCapabilities(_AlexaEntity):
    def default_display_categories(self):
        return [_DisplayCategory.SWITCH]

    def interfaces(self):
        return [_AlexaPowerController(self.entity),
                _AlexaEndpointHealth(self.hass, self.entity)]


@ENTITY_ADAPTERS.register(climate.DOMAIN)
class _ClimateCapabilities(_AlexaEntity):
    def default_display_categories(self):
        return [_DisplayCategory.THERMOSTAT]

    def interfaces(self):
        supported = self.entity.attributes.get(ATTR_SUPPORTED_FEATURES, 0)
        if supported & climate.SUPPORT_ON_OFF:
            yield _AlexaPowerController(self.entity)
        yield _AlexaThermostatController(self.hass, self.entity)
        yield _AlexaTemperatureSensor(self.hass, self.entity)
        yield _AlexaEndpointHealth(self.hass, self.entity)


@ENTITY_ADAPTERS.register(cover.DOMAIN)
class _CoverCapabilities(_AlexaEntity):
    def default_display_categories(self):
        return [_DisplayCategory.DOOR]

    def interfaces(self):
        yield _AlexaPowerController(self.entity)
        supported = self.entity.attributes.get(ATTR_SUPPORTED_FEATURES, 0)
        if supported & cover.SUPPORT_SET_POSITION:
            yield _AlexaPercentageController(self.entity)
        yield _AlexaEndpointHealth(self.hass, self.entity)


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
        yield _AlexaEndpointHealth(self.hass, self.entity)


@ENTITY_ADAPTERS.register(fan.DOMAIN)
class _FanCapabilities(_AlexaEntity):
    def default_display_categories(self):
        return [_DisplayCategory.OTHER]

    def interfaces(self):
        yield _AlexaPowerController(self.entity)
        supported = self.entity.attributes.get(ATTR_SUPPORTED_FEATURES, 0)
        if supported & fan.SUPPORT_SET_SPEED:
            yield _AlexaPercentageController(self.entity)
        yield _AlexaEndpointHealth(self.hass, self.entity)


@ENTITY_ADAPTERS.register(lock.DOMAIN)
class _LockCapabilities(_AlexaEntity):
    def default_display_categories(self):
        return [_DisplayCategory.SMARTLOCK]

    def interfaces(self):
        return [_AlexaLockController(self.entity),
                _AlexaEndpointHealth(self.hass, self.entity)]


@ENTITY_ADAPTERS.register(media_player.const.DOMAIN)
class _MediaPlayerCapabilities(_AlexaEntity):
    def default_display_categories(self):
        return [_DisplayCategory.TV]

    def interfaces(self):
        yield _AlexaEndpointHealth(self.hass, self.entity)

        supported = self.entity.attributes.get(ATTR_SUPPORTED_FEATURES, 0)
        if supported & media_player.const.SUPPORT_VOLUME_SET:
            yield _AlexaSpeaker(self.entity)

        power_features = (media_player.SUPPORT_TURN_ON |
                          media_player.SUPPORT_TURN_OFF)
        if supported & power_features:
            yield _AlexaPowerController(self.entity)

        step_volume_features = (media_player.const.SUPPORT_VOLUME_MUTE |
                                media_player.const.SUPPORT_VOLUME_STEP)
        if supported & step_volume_features:
            yield _AlexaStepSpeaker(self.entity)

        playback_features = (media_player.const.SUPPORT_PLAY |
                             media_player.const.SUPPORT_PAUSE |
                             media_player.const.SUPPORT_STOP |
                             media_player.const.SUPPORT_NEXT_TRACK |
                             media_player.const.SUPPORT_PREVIOUS_TRACK)
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
        if attrs.get(ATTR_UNIT_OF_MEASUREMENT) in (
                TEMP_FAHRENHEIT,
                TEMP_CELSIUS,
        ):
            yield _AlexaTemperatureSensor(self.hass, self.entity)
            yield _AlexaEndpointHealth(self.hass, self.entity)


@ENTITY_ADAPTERS.register(binary_sensor.DOMAIN)
class _BinarySensorCapabilities(_AlexaEntity):
    TYPE_CONTACT = 'contact'
    TYPE_MOTION = 'motion'

    def default_display_categories(self):
        sensor_type = self.get_type()
        if sensor_type is self.TYPE_CONTACT:
            return [_DisplayCategory.CONTACT_SENSOR]
        if sensor_type is self.TYPE_MOTION:
            return [_DisplayCategory.MOTION_SENSOR]

    def interfaces(self):
        sensor_type = self.get_type()
        if sensor_type is self.TYPE_CONTACT:
            yield _AlexaContactSensor(self.hass, self.entity)
        elif sensor_type is self.TYPE_MOTION:
            yield _AlexaMotionSensor(self.hass, self.entity)

        yield _AlexaEndpointHealth(self.hass, self.entity)

    def get_type(self):
        """Return the type of binary sensor."""
        attrs = self.entity.attributes
        if attrs.get(ATTR_DEVICE_CLASS) in (
                'door',
                'garage_door',
                'opening',
                'window',
        ):
            return self.TYPE_CONTACT
        if attrs.get(ATTR_DEVICE_CLASS) == 'motion':
            return self.TYPE_MOTION


class _Cause:
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

    def __init__(self, endpoint, async_get_access_token, should_expose,
                 entity_config=None):
        """Initialize the configuration."""
        self.endpoint = endpoint
        self.async_get_access_token = async_get_access_token
        self.should_expose = should_expose
        self.entity_config = entity_config or {}


async def async_setup(hass, config):
    """Activate Smart Home functionality of Alexa component.

    This is optional, triggered by having a `smart_home:` sub-section in the
    alexa configuration.

    Even if that's disabled, the functionality in this module may still be used
    by the cloud component which will call async_handle_message directly.
    """
    if config.get(CONF_CLIENT_ID) and config.get(CONF_CLIENT_SECRET):
        hass.data[AUTH_KEY] = Auth(hass, config[CONF_CLIENT_ID],
                                   config[CONF_CLIENT_SECRET])

    async_get_access_token = \
        hass.data[AUTH_KEY].async_get_access_token if AUTH_KEY in hass.data \
        else None

    smart_home_config = Config(
        endpoint=config.get(CONF_ENDPOINT),
        async_get_access_token=async_get_access_token,
        should_expose=config[CONF_FILTER],
        entity_config=config.get(CONF_ENTITY_CONFIG),
    )
    hass.http.register_view(SmartHomeView(smart_home_config))

    if AUTH_KEY in hass.data:
        await async_enable_proactive_mode(hass, smart_home_config)


async def async_enable_proactive_mode(hass, smart_home_config):
    """Enable the proactive mode.

    Proactive mode makes this component report state changes to Alexa.
    """
    if smart_home_config.async_get_access_token is None:
        # no function to call to get token
        return

    if await smart_home_config.async_get_access_token() is None:
        # not ready yet
        return

    async def async_entity_state_listener(changed_entity, old_state,
                                          new_state):
        if not smart_home_config.should_expose(changed_entity):
            _LOGGER.debug("Not exposing %s because filtered by config",
                          changed_entity)
            return

        if new_state.domain not in ENTITY_ADAPTERS:
            return

        alexa_changed_entity = \
            ENTITY_ADAPTERS[new_state.domain](hass, smart_home_config,
                                              new_state)

        for interface in alexa_changed_entity.interfaces():
            if interface.properties_proactively_reported():
                await async_send_changereport_message(hass, smart_home_config,
                                                      alexa_changed_entity)
                return

    async_track_state_change(hass, MATCH_ALL, async_entity_state_listener)


class SmartHomeView(http.HomeAssistantView):
    """Expose Smart Home v3 payload interface via HTTP POST."""

    url = SMART_HOME_HTTP_ENDPOINT
    name = 'api:alexa:smart_home'

    def __init__(self, smart_home_config):
        """Initialize."""
        self.smart_home_config = smart_home_config

    async def post(self, request):
        """Handle Alexa Smart Home requests.

        The Smart Home API requires the endpoint to be implemented in AWS
        Lambda, which will need to forward the requests to here and pass back
        the response.
        """
        hass = request.app['hass']
        user = request[http.KEY_HASS_USER]
        message = await request.json()

        _LOGGER.debug("Received Alexa Smart Home request: %s", message)

        response = await async_handle_message(
            hass, self.smart_home_config, message,
            context=ha.Context(user_id=user.id)
        )
        _LOGGER.debug("Sending Alexa Smart Home response: %s", response)
        return b'' if response is None else self.json(response)


class _AlexaDirective:
    def __init__(self, request):
        self._directive = request[API_DIRECTIVE]
        self.namespace = self._directive[API_HEADER]['namespace']
        self.name = self._directive[API_HEADER]['name']
        self.payload = self._directive[API_PAYLOAD]
        self.has_endpoint = API_ENDPOINT in self._directive

        self.entity = self.entity_id = self.endpoint = None

    def load_entity(self, hass, config):
        """Set attributes related to the entity for this request.

        Sets these attributes when self.has_endpoint is True:

        - entity
        - entity_id
        - endpoint

        Behavior when self.has_endpoint is False is undefined.

        Will raise _AlexaInvalidEndpointError if the endpoint in the request is
        malformed or nonexistant.
        """
        _endpoint_id = self._directive[API_ENDPOINT]['endpointId']
        self.entity_id = _endpoint_id.replace('#', '.')

        self.entity = hass.states.get(self.entity_id)
        if not self.entity:
            raise _AlexaInvalidEndpointError(_endpoint_id)

        self.endpoint = ENTITY_ADAPTERS[self.entity.domain](
            hass, config, self.entity)

    def response(self,
                 name='Response',
                 namespace='Alexa',
                 payload=None):
        """Create an API formatted response.

        Async friendly.
        """
        response = _AlexaResponse(name, namespace, payload)

        token = self._directive[API_HEADER].get('correlationToken')
        if token:
            response.set_correlation_token(token)

        if self.has_endpoint:
            response.set_endpoint(self._directive[API_ENDPOINT].copy())

        return response

    def error(
            self,
            namespace='Alexa',
            error_type='INTERNAL_ERROR',
            error_message="",
            payload=None
    ):
        """Create a API formatted error response.

        Async friendly.
        """
        payload = payload or {}
        payload['type'] = error_type
        payload['message'] = error_message

        _LOGGER.info("Request %s/%s error %s: %s",
                     self._directive[API_HEADER]['namespace'],
                     self._directive[API_HEADER]['name'],
                     error_type, error_message)

        return self.response(
            name='ErrorResponse',
            namespace=namespace,
            payload=payload
        )


class _AlexaResponse:
    def __init__(self, name, namespace, payload=None):
        payload = payload or {}
        self._response = {
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

    @property
    def name(self):
        """Return the name of this response."""
        return self._response[API_EVENT][API_HEADER]['name']

    @property
    def namespace(self):
        """Return the namespace of this response."""
        return self._response[API_EVENT][API_HEADER]['namespace']

    def set_correlation_token(self, token):
        """Set the correlationToken.

        This should normally mirror the value from a request, and is set by
        _AlexaDirective.response() usually.
        """
        self._response[API_EVENT][API_HEADER]['correlationToken'] = token

    def set_endpoint_full(self, bearer_token, endpoint_id, cookie=None):
        """Set the endpoint dictionary.

        This is used to send proactive messages to Alexa.
        """
        self._response[API_EVENT][API_ENDPOINT] = {
            API_SCOPE: {
                'type': 'BearerToken',
                'token': bearer_token
            }
        }

        if endpoint_id is not None:
            self._response[API_EVENT][API_ENDPOINT]['endpointId'] = endpoint_id

        if cookie is not None:
            self._response[API_EVENT][API_ENDPOINT]['cookie'] = cookie

    def set_endpoint(self, endpoint):
        """Set the endpoint.

        This should normally mirror the value from a request, and is set by
        _AlexaDirective.response() usually.
        """
        self._response[API_EVENT][API_ENDPOINT] = endpoint

    def _properties(self):
        context = self._response.setdefault(API_CONTEXT, {})
        return context.setdefault('properties', [])

    def add_context_property(self, prop):
        """Add a property to the response context.

        The Alexa response includes a list of properties which provides
        feedback on how states have changed. For example if a user asks,
        "Alexa, set theromstat to 20 degrees", the API expects a response with
        the new value of the property, and Alexa will respond to the user
        "Thermostat set to 20 degrees".

        async_handle_message() will call .merge_context_properties() for every
        request automatically, however often handlers will call services to
        change state but the effects of those changes are applied
        asynchronously. Thus, handlers should call this method to confirm
        changes before returning.
        """
        self._properties().append(prop)

    def merge_context_properties(self, endpoint):
        """Add all properties from given endpoint if not already set.

        Handlers should be using .add_context_property().
        """
        properties = self._properties()
        already_set = {(p['namespace'], p['name']) for p in properties}

        for prop in endpoint.serialize_properties():
            if (prop['namespace'], prop['name']) not in already_set:
                self.add_context_property(prop)

    def serialize(self):
        """Return response as a JSON-able data structure."""
        return self._response


async def async_handle_message(
        hass,
        config,
        request,
        context=None,
        enabled=True,
):
    """Handle incoming API messages.

    If enabled is False, the response to all messagess will be a
    BRIDGE_UNREACHABLE error. This can be used if the API has been disabled in
    configuration.
    """
    assert request[API_DIRECTIVE][API_HEADER]['payloadVersion'] == '3'

    if context is None:
        context = ha.Context()

    directive = _AlexaDirective(request)

    try:
        if not enabled:
            raise _AlexaBridgeUnreachableError(
                'Alexa API not enabled in Home Assistant configuration')

        if directive.has_endpoint:
            directive.load_entity(hass, config)

        funct_ref = HANDLERS.get((directive.namespace, directive.name))
        if funct_ref:
            response = await funct_ref(hass, config, directive, context)
            if directive.has_endpoint:
                response.merge_context_properties(directive.endpoint)
        else:
            _LOGGER.warning(
                "Unsupported API request %s/%s",
                directive.namespace,
                directive.name,
            )
            response = directive.error()
    except _AlexaError as err:
        response = directive.error(
            error_type=err.error_type,
            error_message=err.error_message)

    request_info = {
        'namespace': directive.namespace,
        'name': directive.name,
    }

    if directive.has_endpoint:
        request_info['entity_id'] = directive.entity_id

    hass.bus.async_fire(EVENT_ALEXA_SMART_HOME, {
        'request': request_info,
        'response': {
            'namespace': response.namespace,
            'name': response.name,
        }
    }, context=context)

    return response.serialize()


async def async_send_changereport_message(hass, config, alexa_entity):
    """Send a ChangeReport message for an Alexa entity."""
    token = await config.async_get_access_token()
    if not token:
        _LOGGER.error("Invalid access token.")
        return

    headers = {
        "Authorization": "Bearer {}".format(token)
    }

    endpoint = alexa_entity.entity_id()

    # this sends all the properties of the Alexa Entity, whether they have
    # changed or not. this should be improved, and properties that have not
    # changed should be moved to the 'context' object
    properties = list(alexa_entity.serialize_properties())

    payload = {
        API_CHANGE: {
            'cause': {'type': _Cause.APP_INTERACTION},
            'properties': properties
        }
    }

    message = _AlexaResponse(name='ChangeReport', namespace='Alexa',
                             payload=payload)
    message.set_endpoint_full(token, endpoint)

    message_serialized = message.serialize()

    try:
        session = aiohttp_client.async_get_clientsession(hass)
        with async_timeout.timeout(DEFAULT_TIMEOUT, loop=hass.loop):
            response = await session.post(config.endpoint,
                                          headers=headers,
                                          json=message_serialized,
                                          allow_redirects=True)

    except (asyncio.TimeoutError, aiohttp.ClientError):
        _LOGGER.error("Timeout calling LWA to get auth token.")
        return None

    response_text = await response.text()

    _LOGGER.debug("Sent: %s", json.dumps(message_serialized))
    _LOGGER.debug("Received (%s): %s", response.status, response_text)

    if response.status != 202:
        response_json = json.loads(response_text)
        _LOGGER.error("Error when sending ChangeReport to Alexa: %s: %s",
                      response_json["payload"]["code"],
                      response_json["payload"]["description"])


@HANDLERS.register(('Alexa.Discovery', 'Discover'))
async def async_api_discovery(hass, config, directive, context):
    """Create a API formatted discovery response.

    Async friendly.
    """
    discovery_endpoints = []

    for entity in hass.states.async_all():
        if entity.entity_id in CLOUD_NEVER_EXPOSED_ENTITIES:
            _LOGGER.debug("Not exposing %s because it is never exposed",
                          entity.entity_id)
            continue

        if not config.should_expose(entity.entity_id):
            _LOGGER.debug("Not exposing %s because filtered by config",
                          entity.entity_id)
            continue

        if entity.domain not in ENTITY_ADAPTERS:
            continue
        alexa_entity = ENTITY_ADAPTERS[entity.domain](hass, config, entity)

        endpoint = {
            'displayCategories': alexa_entity.display_categories(),
            'cookie': {},
            'endpointId': alexa_entity.entity_id(),
            'friendlyName': alexa_entity.friendly_name(),
            'description': alexa_entity.description(),
            'manufacturerName': 'Home Assistant',
        }

        endpoint['capabilities'] = [
            i.serialize_discovery() for i in alexa_entity.interfaces()]

        if not endpoint['capabilities']:
            _LOGGER.debug(
                "Not exposing %s because it has no capabilities",
                entity.entity_id)
            continue
        discovery_endpoints.append(endpoint)

    return directive.response(
        name='Discover.Response',
        namespace='Alexa.Discovery',
        payload={'endpoints': discovery_endpoints},
    )


@HANDLERS.register(('Alexa.Authorization', 'AcceptGrant'))
async def async_api_accept_grant(hass, config, directive, context):
    """Create a API formatted AcceptGrant response.

    Async friendly.
    """
    auth_code = directive.payload['grant']['code']
    _LOGGER.debug("AcceptGrant code: %s", auth_code)

    if AUTH_KEY in hass.data:
        await hass.data[AUTH_KEY].async_do_auth(auth_code)
        await async_enable_proactive_mode(hass, config)

    return directive.response(
        name='AcceptGrant.Response',
        namespace='Alexa.Authorization',
        payload={})


@HANDLERS.register(('Alexa.PowerController', 'TurnOn'))
async def async_api_turn_on(hass, config, directive, context):
    """Process a turn on request."""
    entity = directive.entity
    domain = entity.domain
    if domain == group.DOMAIN:
        domain = ha.DOMAIN

    service = SERVICE_TURN_ON
    if domain == cover.DOMAIN:
        service = cover.SERVICE_OPEN_COVER

    await hass.services.async_call(domain, service, {
        ATTR_ENTITY_ID: entity.entity_id
    }, blocking=False, context=context)

    return directive.response()


@HANDLERS.register(('Alexa.PowerController', 'TurnOff'))
async def async_api_turn_off(hass, config, directive, context):
    """Process a turn off request."""
    entity = directive.entity
    domain = entity.domain
    if entity.domain == group.DOMAIN:
        domain = ha.DOMAIN

    service = SERVICE_TURN_OFF
    if entity.domain == cover.DOMAIN:
        service = cover.SERVICE_CLOSE_COVER

    await hass.services.async_call(domain, service, {
        ATTR_ENTITY_ID: entity.entity_id
    }, blocking=False, context=context)

    return directive.response()


@HANDLERS.register(('Alexa.BrightnessController', 'SetBrightness'))
async def async_api_set_brightness(hass, config, directive, context):
    """Process a set brightness request."""
    entity = directive.entity
    brightness = int(directive.payload['brightness'])

    await hass.services.async_call(entity.domain, SERVICE_TURN_ON, {
        ATTR_ENTITY_ID: entity.entity_id,
        light.ATTR_BRIGHTNESS_PCT: brightness,
    }, blocking=False, context=context)

    return directive.response()


@HANDLERS.register(('Alexa.BrightnessController', 'AdjustBrightness'))
async def async_api_adjust_brightness(hass, config, directive, context):
    """Process an adjust brightness request."""
    entity = directive.entity
    brightness_delta = int(directive.payload['brightnessDelta'])

    # read current state
    try:
        current = math.floor(
            int(entity.attributes.get(light.ATTR_BRIGHTNESS)) / 255 * 100)
    except ZeroDivisionError:
        current = 0

    # set brightness
    brightness = max(0, brightness_delta + current)
    await hass.services.async_call(entity.domain, SERVICE_TURN_ON, {
        ATTR_ENTITY_ID: entity.entity_id,
        light.ATTR_BRIGHTNESS_PCT: brightness,
    }, blocking=False, context=context)

    return directive.response()


@HANDLERS.register(('Alexa.ColorController', 'SetColor'))
async def async_api_set_color(hass, config, directive, context):
    """Process a set color request."""
    entity = directive.entity
    rgb = color_util.color_hsb_to_RGB(
        float(directive.payload['color']['hue']),
        float(directive.payload['color']['saturation']),
        float(directive.payload['color']['brightness'])
    )

    await hass.services.async_call(entity.domain, SERVICE_TURN_ON, {
        ATTR_ENTITY_ID: entity.entity_id,
        light.ATTR_RGB_COLOR: rgb,
    }, blocking=False, context=context)

    return directive.response()


@HANDLERS.register(('Alexa.ColorTemperatureController', 'SetColorTemperature'))
async def async_api_set_color_temperature(hass, config, directive, context):
    """Process a set color temperature request."""
    entity = directive.entity
    kelvin = int(directive.payload['colorTemperatureInKelvin'])

    await hass.services.async_call(entity.domain, SERVICE_TURN_ON, {
        ATTR_ENTITY_ID: entity.entity_id,
        light.ATTR_KELVIN: kelvin,
    }, blocking=False, context=context)

    return directive.response()


@HANDLERS.register(
    ('Alexa.ColorTemperatureController', 'DecreaseColorTemperature'))
async def async_api_decrease_color_temp(hass, config, directive, context):
    """Process a decrease color temperature request."""
    entity = directive.entity
    current = int(entity.attributes.get(light.ATTR_COLOR_TEMP))
    max_mireds = int(entity.attributes.get(light.ATTR_MAX_MIREDS))

    value = min(max_mireds, current + 50)
    await hass.services.async_call(entity.domain, SERVICE_TURN_ON, {
        ATTR_ENTITY_ID: entity.entity_id,
        light.ATTR_COLOR_TEMP: value,
    }, blocking=False, context=context)

    return directive.response()


@HANDLERS.register(
    ('Alexa.ColorTemperatureController', 'IncreaseColorTemperature'))
async def async_api_increase_color_temp(hass, config, directive, context):
    """Process an increase color temperature request."""
    entity = directive.entity
    current = int(entity.attributes.get(light.ATTR_COLOR_TEMP))
    min_mireds = int(entity.attributes.get(light.ATTR_MIN_MIREDS))

    value = max(min_mireds, current - 50)
    await hass.services.async_call(entity.domain, SERVICE_TURN_ON, {
        ATTR_ENTITY_ID: entity.entity_id,
        light.ATTR_COLOR_TEMP: value,
    }, blocking=False, context=context)

    return directive.response()


@HANDLERS.register(('Alexa.SceneController', 'Activate'))
async def async_api_activate(hass, config, directive, context):
    """Process an activate request."""
    entity = directive.entity
    domain = entity.domain

    await hass.services.async_call(domain, SERVICE_TURN_ON, {
        ATTR_ENTITY_ID: entity.entity_id
    }, blocking=False, context=context)

    payload = {
        'cause': {'type': _Cause.VOICE_INTERACTION},
        'timestamp': '%sZ' % (datetime.utcnow().isoformat(),)
    }

    return directive.response(
        name='ActivationStarted',
        namespace='Alexa.SceneController',
        payload=payload,
    )


@HANDLERS.register(('Alexa.SceneController', 'Deactivate'))
async def async_api_deactivate(hass, config, directive, context):
    """Process a deactivate request."""
    entity = directive.entity
    domain = entity.domain

    await hass.services.async_call(domain, SERVICE_TURN_OFF, {
        ATTR_ENTITY_ID: entity.entity_id
    }, blocking=False, context=context)

    payload = {
        'cause': {'type': _Cause.VOICE_INTERACTION},
        'timestamp': '%sZ' % (datetime.utcnow().isoformat(),)
    }

    return directive.response(
        name='DeactivationStarted',
        namespace='Alexa.SceneController',
        payload=payload,
    )


@HANDLERS.register(('Alexa.PercentageController', 'SetPercentage'))
async def async_api_set_percentage(hass, config, directive, context):
    """Process a set percentage request."""
    entity = directive.entity
    percentage = int(directive.payload['percentage'])
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

    await hass.services.async_call(
        entity.domain, service, data, blocking=False, context=context)

    return directive.response()


@HANDLERS.register(('Alexa.PercentageController', 'AdjustPercentage'))
async def async_api_adjust_percentage(hass, config, directive, context):
    """Process an adjust percentage request."""
    entity = directive.entity
    percentage_delta = int(directive.payload['percentageDelta'])
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

    await hass.services.async_call(
        entity.domain, service, data, blocking=False, context=context)

    return directive.response()


@HANDLERS.register(('Alexa.LockController', 'Lock'))
async def async_api_lock(hass, config, directive, context):
    """Process a lock request."""
    entity = directive.entity
    await hass.services.async_call(entity.domain, SERVICE_LOCK, {
        ATTR_ENTITY_ID: entity.entity_id
    }, blocking=False, context=context)

    response = directive.response()
    response.add_context_property({
        'name': 'lockState',
        'namespace': 'Alexa.LockController',
        'value': 'LOCKED'
    })
    return response


# Not supported by Alexa yet
@HANDLERS.register(('Alexa.LockController', 'Unlock'))
async def async_api_unlock(hass, config, directive, context):
    """Process an unlock request."""
    entity = directive.entity
    await hass.services.async_call(entity.domain, SERVICE_UNLOCK, {
        ATTR_ENTITY_ID: entity.entity_id
    }, blocking=False, context=context)

    return directive.response()


@HANDLERS.register(('Alexa.Speaker', 'SetVolume'))
async def async_api_set_volume(hass, config, directive, context):
    """Process a set volume request."""
    volume = round(float(directive.payload['volume'] / 100), 2)
    entity = directive.entity

    data = {
        ATTR_ENTITY_ID: entity.entity_id,
        media_player.const.ATTR_MEDIA_VOLUME_LEVEL: volume,
    }

    await hass.services.async_call(
        entity.domain, SERVICE_VOLUME_SET,
        data, blocking=False, context=context)

    return directive.response()


@HANDLERS.register(('Alexa.InputController', 'SelectInput'))
async def async_api_select_input(hass, config, directive, context):
    """Process a set input request."""
    media_input = directive.payload['input']
    entity = directive.entity

    # attempt to map the ALL UPPERCASE payload name to a source
    source_list = entity.attributes[
        media_player.const.ATTR_INPUT_SOURCE_LIST] or []
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
        raise _AlexaInvalidValueError(msg)

    data = {
        ATTR_ENTITY_ID: entity.entity_id,
        media_player.const.ATTR_INPUT_SOURCE: media_input,
    }

    await hass.services.async_call(
        entity.domain, media_player.SERVICE_SELECT_SOURCE,
        data, blocking=False, context=context)

    return directive.response()


@HANDLERS.register(('Alexa.Speaker', 'AdjustVolume'))
async def async_api_adjust_volume(hass, config, directive, context):
    """Process an adjust volume request."""
    volume_delta = int(directive.payload['volume'])

    entity = directive.entity
    current_level = entity.attributes.get(
        media_player.const.ATTR_MEDIA_VOLUME_LEVEL)

    # read current state
    try:
        current = math.floor(int(current_level * 100))
    except ZeroDivisionError:
        current = 0

    volume = float(max(0, volume_delta + current) / 100)

    data = {
        ATTR_ENTITY_ID: entity.entity_id,
        media_player.const.ATTR_MEDIA_VOLUME_LEVEL: volume,
    }

    await hass.services.async_call(
        entity.domain, SERVICE_VOLUME_SET,
        data, blocking=False, context=context)

    return directive.response()


@HANDLERS.register(('Alexa.StepSpeaker', 'AdjustVolume'))
async def async_api_adjust_volume_step(hass, config, directive, context):
    """Process an adjust volume step request."""
    # media_player volume up/down service does not support specifying steps
    # each component handles it differently e.g. via config.
    # For now we use the volumeSteps returned to figure out if we
    # should step up/down
    volume_step = directive.payload['volumeSteps']
    entity = directive.entity

    data = {
        ATTR_ENTITY_ID: entity.entity_id,
    }

    if volume_step > 0:
        await hass.services.async_call(
            entity.domain, SERVICE_VOLUME_UP,
            data, blocking=False, context=context)
    elif volume_step < 0:
        await hass.services.async_call(
            entity.domain, SERVICE_VOLUME_DOWN,
            data, blocking=False, context=context)

    return directive.response()


@HANDLERS.register(('Alexa.StepSpeaker', 'SetMute'))
@HANDLERS.register(('Alexa.Speaker', 'SetMute'))
async def async_api_set_mute(hass, config, directive, context):
    """Process a set mute request."""
    mute = bool(directive.payload['mute'])
    entity = directive.entity

    data = {
        ATTR_ENTITY_ID: entity.entity_id,
        media_player.const.ATTR_MEDIA_VOLUME_MUTED: mute,
    }

    await hass.services.async_call(
        entity.domain, SERVICE_VOLUME_MUTE,
        data, blocking=False, context=context)

    return directive.response()


@HANDLERS.register(('Alexa.PlaybackController', 'Play'))
async def async_api_play(hass, config, directive, context):
    """Process a play request."""
    entity = directive.entity
    data = {
        ATTR_ENTITY_ID: entity.entity_id
    }

    await hass.services.async_call(
        entity.domain, SERVICE_MEDIA_PLAY,
        data, blocking=False, context=context)

    return directive.response()


@HANDLERS.register(('Alexa.PlaybackController', 'Pause'))
async def async_api_pause(hass, config, directive, context):
    """Process a pause request."""
    entity = directive.entity
    data = {
        ATTR_ENTITY_ID: entity.entity_id
    }

    await hass.services.async_call(
        entity.domain, SERVICE_MEDIA_PAUSE,
        data, blocking=False, context=context)

    return directive.response()


@HANDLERS.register(('Alexa.PlaybackController', 'Stop'))
async def async_api_stop(hass, config, directive, context):
    """Process a stop request."""
    entity = directive.entity
    data = {
        ATTR_ENTITY_ID: entity.entity_id
    }

    await hass.services.async_call(
        entity.domain, SERVICE_MEDIA_STOP,
        data, blocking=False, context=context)

    return directive.response()


@HANDLERS.register(('Alexa.PlaybackController', 'Next'))
async def async_api_next(hass, config, directive, context):
    """Process a next request."""
    entity = directive.entity
    data = {
        ATTR_ENTITY_ID: entity.entity_id
    }

    await hass.services.async_call(
        entity.domain, SERVICE_MEDIA_NEXT_TRACK,
        data, blocking=False, context=context)

    return directive.response()


@HANDLERS.register(('Alexa.PlaybackController', 'Previous'))
async def async_api_previous(hass, config, directive, context):
    """Process a previous request."""
    entity = directive.entity
    data = {
        ATTR_ENTITY_ID: entity.entity_id
    }

    await hass.services.async_call(
        entity.domain, SERVICE_MEDIA_PREVIOUS_TRACK,
        data, blocking=False, context=context)

    return directive.response()


def temperature_from_object(hass, temp_obj, interval=False):
    """Get temperature from Temperature object in requested unit."""
    to_unit = hass.config.units.temperature_unit
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
async def async_api_set_target_temp(hass, config, directive, context):
    """Process a set target temperature request."""
    entity = directive.entity
    min_temp = entity.attributes.get(climate.ATTR_MIN_TEMP)
    max_temp = entity.attributes.get(climate.ATTR_MAX_TEMP)
    unit = hass.config.units.temperature_unit

    data = {
        ATTR_ENTITY_ID: entity.entity_id
    }

    payload = directive.payload
    response = directive.response()
    if 'targetSetpoint' in payload:
        temp = temperature_from_object(hass, payload['targetSetpoint'])
        if temp < min_temp or temp > max_temp:
            raise _AlexaTempRangeError(hass, temp, min_temp, max_temp)
        data[ATTR_TEMPERATURE] = temp
        response.add_context_property({
            'name': 'targetSetpoint',
            'namespace': 'Alexa.ThermostatController',
            'value': {'value': temp, 'scale': API_TEMP_UNITS[unit]},
        })
    if 'lowerSetpoint' in payload:
        temp_low = temperature_from_object(hass, payload['lowerSetpoint'])
        if temp_low < min_temp or temp_low > max_temp:
            raise _AlexaTempRangeError(hass, temp_low, min_temp, max_temp)
        data[climate.ATTR_TARGET_TEMP_LOW] = temp_low
        response.add_context_property({
            'name': 'lowerSetpoint',
            'namespace': 'Alexa.ThermostatController',
            'value': {'value': temp_low, 'scale': API_TEMP_UNITS[unit]},
        })
    if 'upperSetpoint' in payload:
        temp_high = temperature_from_object(hass, payload['upperSetpoint'])
        if temp_high < min_temp or temp_high > max_temp:
            raise _AlexaTempRangeError(hass, temp_high, min_temp, max_temp)
        data[climate.ATTR_TARGET_TEMP_HIGH] = temp_high
        response.add_context_property({
            'name': 'upperSetpoint',
            'namespace': 'Alexa.ThermostatController',
            'value': {'value': temp_high, 'scale': API_TEMP_UNITS[unit]},
        })

    await hass.services.async_call(
        entity.domain, climate.SERVICE_SET_TEMPERATURE, data, blocking=False,
        context=context)

    return response


@HANDLERS.register(('Alexa.ThermostatController', 'AdjustTargetTemperature'))
async def async_api_adjust_target_temp(hass, config, directive, context):
    """Process an adjust target temperature request."""
    entity = directive.entity
    min_temp = entity.attributes.get(climate.ATTR_MIN_TEMP)
    max_temp = entity.attributes.get(climate.ATTR_MAX_TEMP)
    unit = hass.config.units.temperature_unit

    temp_delta = temperature_from_object(
        hass, directive.payload['targetSetpointDelta'], interval=True)
    target_temp = float(entity.attributes.get(ATTR_TEMPERATURE)) + temp_delta

    if target_temp < min_temp or target_temp > max_temp:
        raise _AlexaTempRangeError(hass, target_temp, min_temp, max_temp)

    data = {
        ATTR_ENTITY_ID: entity.entity_id,
        ATTR_TEMPERATURE: target_temp,
    }

    response = directive.response()
    await hass.services.async_call(
        entity.domain, climate.SERVICE_SET_TEMPERATURE, data, blocking=False,
        context=context)
    response.add_context_property({
        'name': 'targetSetpoint',
        'namespace': 'Alexa.ThermostatController',
        'value': {'value': target_temp, 'scale': API_TEMP_UNITS[unit]},
    })

    return response


@HANDLERS.register(('Alexa.ThermostatController', 'SetThermostatMode'))
async def async_api_set_thermostat_mode(hass, config, directive, context):
    """Process a set thermostat mode request."""
    entity = directive.entity
    mode = directive.payload['thermostatMode']
    mode = mode if isinstance(mode, str) else mode['value']

    operation_list = entity.attributes.get(climate.ATTR_OPERATION_LIST)
    ha_mode = next(
        (k for k, v in API_THERMOSTAT_MODES.items() if v == mode),
        None
    )
    if ha_mode not in operation_list:
        msg = 'The requested thermostat mode {} is not supported'.format(mode)
        raise _AlexaUnsupportedThermostatModeError(msg)

    data = {
        ATTR_ENTITY_ID: entity.entity_id,
        climate.ATTR_OPERATION_MODE: ha_mode,
    }

    response = directive.response()
    await hass.services.async_call(
        entity.domain, climate.SERVICE_SET_OPERATION_MODE, data,
        blocking=False, context=context)
    response.add_context_property({
        'name': 'thermostatMode',
        'namespace': 'Alexa.ThermostatController',
        'value': mode,
    })

    return response


@HANDLERS.register(('Alexa', 'ReportState'))
async def async_api_reportstate(hass, config, directive, context):
    """Process a ReportState request."""
    return directive.response(name='StateReport')
