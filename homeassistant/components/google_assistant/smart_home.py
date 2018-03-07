"""Support for Google Assistant Smart Home API."""
import asyncio
import logging

# Typing imports
# pylint: disable=using-constant-test,unused-import,ungrouped-imports
# if False:
from aiohttp.web import Request, Response  # NOQA
from typing import Dict, Tuple, Any, Optional  # NOQA
from homeassistant.helpers.entity import Entity  # NOQA
from homeassistant.core import HomeAssistant  # NOQA
from homeassistant.util import color
from homeassistant.util.unit_system import UnitSystem  # NOQA
from homeassistant.util.decorator import Registry

from homeassistant.const import (
    ATTR_SUPPORTED_FEATURES, ATTR_ENTITY_ID, ATTR_UNIT_OF_MEASUREMENT,
    STATE_OFF, SERVICE_TURN_OFF, SERVICE_TURN_ON,
    TEMP_CELSIUS, CONF_NAME
)
from homeassistant.components import (
    switch, light, cover, media_player, group, fan, scene, script, climate,
)
from homeassistant.util.unit_system import METRIC_SYSTEM

from .const import (
    COMMAND_COLOR,
    COMMAND_BRIGHTNESS, COMMAND_ONOFF, COMMAND_ACTIVATESCENE,
    COMMAND_THERMOSTAT_TEMPERATURE_SETPOINT,
    COMMAND_THERMOSTAT_TEMPERATURE_SET_RANGE, COMMAND_THERMOSTAT_SET_MODE,
    TRAIT_ONOFF, TRAIT_BRIGHTNESS, TRAIT_COLOR_TEMP,
    TRAIT_RGB_COLOR, TRAIT_SCENE, TRAIT_TEMPERATURE_SETTING,
    TYPE_LIGHT, TYPE_SCENE, TYPE_SWITCH, TYPE_THERMOSTAT,
    CONF_ALIASES, CONF_ROOM_HINT, CLIMATE_SUPPORTED_MODES,
    CLIMATE_MODE_HEATCOOL
)
from . import trait

HANDLERS = Registry()
QUERY_HANDLERS = Registry()
_LOGGER = logging.getLogger(__name__)


class _GoogleEntity:
    """Adaptation of Entity expressed in Google's terms."""

    def __init__(self, config, state):
        self.config = config
        self.state = state

    def traits(self):
        """Return traits for entity."""
        state = self.state
        domain = state.domain
        features = state.attributes.get(ATTR_SUPPORTED_FEATURES, 0)
        unit = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)

        return [Trait(state) for Trait in trait.TRAITS
                if Trait.supported(domain, features, unit)]

    def sync_serialize(self):
        """Serialize entity for a SYNC response.

        https://developers.google.com/actions/smarthome/create-app#actiondevicessync
        """
        traits = self.traits()
        state = self.state

        # Found no supported traits for this entity
        if not traits:
            return None

        entity_config = self.config.entity_config.get(state.entity_id, {})

        # class_data = MAPPING_COMPONENT.get(google_domain or entity.domain)

        # if class_data is None:
        #     return None

        device = {
            'id': state.entity_id,
            'name': {
                'name': entity_config.get(CONF_NAME) or state.name
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


DOMAIN_TO_GOOGLE_TYPES = {
    group.DOMAIN: TYPE_SWITCH,
    scene.DOMAIN: TYPE_SCENE,
    script.DOMAIN: TYPE_SCENE,
    switch.DOMAIN: TYPE_SWITCH,
    fan.DOMAIN: TYPE_SWITCH,
    light.DOMAIN: TYPE_LIGHT,
    cover.DOMAIN: TYPE_SWITCH,
    media_player.DOMAIN: TYPE_SWITCH,
    climate.DOMAIN: TYPE_THERMOSTAT,
}


# Mapping is [actions schema, primary trait, optional features]
# optional is SUPPORT_* = (trait, command)
MAPPING_COMPONENT = {
    group.DOMAIN: [TYPE_SWITCH, TRAIT_ONOFF, None],
    scene.DOMAIN: [TYPE_SCENE, TRAIT_SCENE, None],
    script.DOMAIN: [TYPE_SCENE, TRAIT_SCENE, None],
    switch.DOMAIN: [TYPE_SWITCH, TRAIT_ONOFF, None],
    fan.DOMAIN: [TYPE_SWITCH, TRAIT_ONOFF, None],
    light.DOMAIN: [
        TYPE_LIGHT, TRAIT_ONOFF, {
            light.SUPPORT_BRIGHTNESS: TRAIT_BRIGHTNESS,
            light.SUPPORT_RGB_COLOR: TRAIT_RGB_COLOR,
            light.SUPPORT_COLOR_TEMP: TRAIT_COLOR_TEMP,
        }
    ],
    cover.DOMAIN: [
        TYPE_SWITCH, TRAIT_ONOFF, {
            cover.SUPPORT_SET_POSITION: TRAIT_BRIGHTNESS
        }
    ],
    media_player.DOMAIN: [
        TYPE_SWITCH, TRAIT_ONOFF, {
            media_player.SUPPORT_VOLUME_SET: TRAIT_BRIGHTNESS
        }
    ],
    climate.DOMAIN: [TYPE_THERMOSTAT, TRAIT_TEMPERATURE_SETTING, None],
}  # type: Dict[str, list]


"""Error code used for SmartHomeError class."""
ERROR_NOT_SUPPORTED = "notSupported"


class SmartHomeError(Exception):
    """Google Assistant Smart Home errors."""

    def __init__(self, code, msg):
        """Log error code."""
        super(SmartHomeError, self).__init__(msg)
        _LOGGER.error(
            "An error has occurred in Google SmartHome: %s."
            "Error code: %s", msg, code
        )
        self.code = code


class Config:
    """Hold the configuration for Google Assistant."""

    def __init__(self, should_expose, agent_user_id, entity_config=None):
        """Initialize the configuration."""
        self.should_expose = should_expose
        self.agent_user_id = agent_user_id
        self.entity_config = entity_config or {}


def celsius(deg: Optional[float], units: UnitSystem) -> Optional[float]:
    """Convert a float to Celsius and rounds to one decimal place."""
    if deg is None:
        return None
    return round(METRIC_SYSTEM.temperature(deg, units.temperature_unit), 1)


@QUERY_HANDLERS.register(climate.DOMAIN)
def query_response_climate(
        entity: Entity, config: Config, units: UnitSystem) -> dict:
    """Convert a climate entity to a QUERY response."""
    mode = entity.attributes.get(climate.ATTR_OPERATION_MODE)
    if mode is None:
        mode = entity.state
    mode = mode.lower()
    if mode not in CLIMATE_SUPPORTED_MODES:
        mode = 'heat'
    attrs = entity.attributes
    response = {
        'thermostatMode': mode,
        'thermostatTemperatureSetpoint':
        celsius(attrs.get(climate.ATTR_TEMPERATURE), units),
        'thermostatTemperatureAmbient':
        celsius(attrs.get(climate.ATTR_CURRENT_TEMPERATURE), units),
        'thermostatTemperatureSetpointHigh':
        celsius(attrs.get(climate.ATTR_TARGET_TEMP_HIGH), units),
        'thermostatTemperatureSetpointLow':
        celsius(attrs.get(climate.ATTR_TARGET_TEMP_LOW), units),
        'thermostatHumidityAmbient':
        attrs.get(climate.ATTR_CURRENT_HUMIDITY),
    }
    return {k: v for k, v in response.items() if v is not None}


@QUERY_HANDLERS.register(media_player.DOMAIN)
def query_response_media_player(
        entity: Entity, config: Config, units: UnitSystem) -> dict:
    """Convert a media_player entity to a QUERY response."""
    level = entity.attributes.get(
        media_player.ATTR_MEDIA_VOLUME_LEVEL,
        1.0 if entity.state != STATE_OFF else 0.0)
    # Convert 0.0-1.0 to 0-255
    brightness = int(level * 100)

    return {'brightness': brightness}


@QUERY_HANDLERS.register(light.DOMAIN)
def query_response_light(
        entity: Entity, config: Config, units: UnitSystem) -> dict:
    """Convert a light entity to a QUERY response."""
    response = {}  # type: Dict[str, Any]

    brightness = entity.attributes.get(light.ATTR_BRIGHTNESS)
    if brightness is not None:
        response['brightness'] = int(100 * (brightness / 255))

    supported_features = entity.attributes.get(ATTR_SUPPORTED_FEATURES, 0)
    if supported_features & \
       (light.SUPPORT_COLOR_TEMP | light.SUPPORT_RGB_COLOR):
        response['color'] = {}

        if entity.attributes.get(light.ATTR_COLOR_TEMP) is not None:
            response['color']['temperature'] = \
                int(round(color.color_temperature_mired_to_kelvin(
                    entity.attributes.get(light.ATTR_COLOR_TEMP))))

        if entity.attributes.get(light.ATTR_COLOR_NAME) is not None:
            response['color']['name'] = \
                entity.attributes.get(light.ATTR_COLOR_NAME)

        if entity.attributes.get(light.ATTR_RGB_COLOR) is not None:
            color_rgb = entity.attributes.get(light.ATTR_RGB_COLOR)
            if color_rgb is not None:
                response['color']['spectrumRGB'] = \
                    int(color.color_rgb_to_hex(
                        color_rgb[0], color_rgb[1], color_rgb[2]), 16)

    return response


def query_device(entity: Entity, config: Config, units: UnitSystem) -> dict:
    """Take an entity and return a properly formatted device object."""
    state = entity.state != STATE_OFF
    defaults = {
        'on': state,
        'online': True
    }

    handler = QUERY_HANDLERS.get(entity.domain)
    if callable(handler):
        defaults.update(handler(entity, config, units))

    return defaults


# erroneous bug on old pythons and pylint
# https://github.com/PyCQA/pylint/issues/1212
# pylint: disable=invalid-sequence-index
def determine_service(
        entity_id: str, command: str, params: dict,
        units: UnitSystem) -> Tuple[str, dict]:
    """
    Determine service and service_data.

    Attempt to return a tuple of service and service_data based on the entity
    and action requested.
    """
    _LOGGER.debug("Handling command %s with data %s", command, params)
    domain = entity_id.split('.')[0]
    service_data = {ATTR_ENTITY_ID: entity_id}  # type: Dict[str, Any]
    # special media_player handling
    if domain == media_player.DOMAIN and command == COMMAND_BRIGHTNESS:
        brightness = params.get('brightness', 0)
        service_data[media_player.ATTR_MEDIA_VOLUME_LEVEL] = brightness / 100
        return (media_player.SERVICE_VOLUME_SET, service_data)

    # special cover handling
    if domain == cover.DOMAIN:
        if command == COMMAND_BRIGHTNESS:
            service_data['position'] = params.get('brightness', 0)
            return (cover.SERVICE_SET_COVER_POSITION, service_data)
        if command == COMMAND_ONOFF and params.get('on') is True:
            return (cover.SERVICE_OPEN_COVER, service_data)
        return (cover.SERVICE_CLOSE_COVER, service_data)

    # special climate handling
    if domain == climate.DOMAIN:
        if command == COMMAND_THERMOSTAT_TEMPERATURE_SETPOINT:
            service_data['temperature'] = \
                units.temperature(
                    params['thermostatTemperatureSetpoint'], TEMP_CELSIUS)
            return (climate.SERVICE_SET_TEMPERATURE, service_data)
        if command == COMMAND_THERMOSTAT_TEMPERATURE_SET_RANGE:
            service_data['target_temp_high'] = units.temperature(
                params.get('thermostatTemperatureSetpointHigh', 25),
                TEMP_CELSIUS)
            service_data['target_temp_low'] = units.temperature(
                params.get('thermostatTemperatureSetpointLow', 18),
                TEMP_CELSIUS)
            return (climate.SERVICE_SET_TEMPERATURE, service_data)
        if command == COMMAND_THERMOSTAT_SET_MODE:
            mode = params['thermostatMode']

            if mode == CLIMATE_MODE_HEATCOOL:
                mode = climate.STATE_AUTO

            service_data['operation_mode'] = mode
            return (climate.SERVICE_SET_OPERATION_MODE, service_data)

    if command == COMMAND_BRIGHTNESS:
        brightness = params.get('brightness')
        service_data['brightness'] = int(brightness / 100 * 255)
        return (SERVICE_TURN_ON, service_data)

    if command == COMMAND_COLOR:
        color_data = params.get('color')
        if color_data is not None:
            if color_data.get('temperature', 0) > 0:
                service_data[light.ATTR_KELVIN] = color_data.get('temperature')
                return (SERVICE_TURN_ON, service_data)
            if color_data.get('spectrumRGB', 0) > 0:
                # blue is 255 so pad up to 6 chars
                hex_value = \
                    ('%0x' % int(color_data.get('spectrumRGB'))).zfill(6)
                service_data[light.ATTR_RGB_COLOR] = \
                    color.rgb_hex_to_rgb_list(hex_value)
                return (SERVICE_TURN_ON, service_data)

    if command == COMMAND_ACTIVATESCENE:
        return (SERVICE_TURN_ON, service_data)

    if COMMAND_ONOFF == command:
        if params.get('on') is True:
            return (SERVICE_TURN_ON, service_data)
        return (SERVICE_TURN_OFF, service_data)

    return (None, service_data)


@asyncio.coroutine
def async_handle_message(hass, config, message):
    """Handle incoming API messages."""
    request_id = message.get('requestId')  # type: str
    inputs = message.get('inputs')  # type: list

    if len(inputs) > 1:
        _LOGGER.warning('Got unexpected more than 1 input. %s', message)

    # Only use first input
    intent = inputs[0].get('intent')
    payload = inputs[0].get('payload')

    handler = HANDLERS.get(intent)

    if handler:
        result = yield from handler(hass, config, payload)
    else:
        result = {'errorCode': 'protocolError'}

    return {'requestId': request_id, 'payload': result}


@HANDLERS.register('action.devices.SYNC')
@asyncio.coroutine
def async_devices_sync(hass, config: Config, payload):
    """Handle action.devices.SYNC request."""
    devices = []
    for state in hass.states.async_all():
        if not config.should_expose(state):
            continue

        entity = _GoogleEntity(config, state)
        serialized = entity.sync_serialize()

        if serialized is None:
            _LOGGER.warning("No mapping for %s domain", entity.state)
            continue

        devices.append(serialized)

    return {
        'agentUserId': config.agent_user_id,
        'devices': devices,
    }


@HANDLERS.register('action.devices.QUERY')
@asyncio.coroutine
def async_devices_query(hass, config, payload):
    """Handle action.devices.QUERY request."""
    devices = {}
    for device in payload.get('devices', []):
        devid = device.get('id')
        # In theory this should never happen
        if not devid:
            _LOGGER.error('Device missing ID: %s', device)
            continue

        state = hass.states.get(devid)
        if not state:
            # If we can't find a state, the device is offline
            devices[devid] = {'online': False}
        else:
            try:
                devices[devid] = query_device(state, config, hass.config.units)
            except SmartHomeError as error:
                devices[devid] = {'errorCode': error.code}

    return {'devices': devices}


@HANDLERS.register('action.devices.EXECUTE')
@asyncio.coroutine
def handle_devices_execute(hass, config, payload):
    """Handle action.devices.EXECUTE request."""
    commands = []
    for command in payload.get('commands', []):
        ent_ids = [ent.get('id') for ent in command.get('devices', [])]
        for execution in command.get('execution'):
            for eid in ent_ids:
                success = False
                domain = eid.split('.')[0]
                (service, service_data) = determine_service(
                    eid, execution.get('command'), execution.get('params'),
                    hass.config.units)
                if domain == "group":
                    domain = "homeassistant"
                success = yield from hass.services.async_call(
                    domain, service, service_data, blocking=True)
                result = {"ids": [eid], "states": {}}
                if success:
                    result['status'] = 'SUCCESS'
                else:
                    result['status'] = 'ERROR'
                commands.append(result)

    return {'commands': commands}
