"""Support for Google Assistant Smart Home API."""
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

from homeassistant.const import (
    ATTR_SUPPORTED_FEATURES, ATTR_ENTITY_ID,
    CONF_FRIENDLY_NAME, STATE_OFF,
    SERVICE_TURN_OFF, SERVICE_TURN_ON,
    TEMP_FAHRENHEIT, TEMP_CELSIUS,
)
from homeassistant.components import (
    switch, light, cover, media_player, group, fan, scene, script, climate
)
from homeassistant.util.unit_system import METRIC_SYSTEM

from .const import (
    ATTR_GOOGLE_ASSISTANT_NAME, COMMAND_COLOR,
    ATTR_GOOGLE_ASSISTANT_TYPE,
    COMMAND_BRIGHTNESS, COMMAND_ONOFF, COMMAND_ACTIVATESCENE,
    COMMAND_THERMOSTAT_TEMPERATURE_SETPOINT,
    COMMAND_THERMOSTAT_TEMPERATURE_SET_RANGE, COMMAND_THERMOSTAT_SET_MODE,
    TRAIT_ONOFF, TRAIT_BRIGHTNESS, TRAIT_COLOR_TEMP,
    TRAIT_RGB_COLOR, TRAIT_SCENE, TRAIT_TEMPERATURE_SETTING,
    TYPE_LIGHT, TYPE_SCENE, TYPE_SWITCH, TYPE_THERMOSTAT,
    CONF_ALIASES, CLIMATE_SUPPORTED_MODES
)

_LOGGER = logging.getLogger(__name__)

# Mapping is [actions schema, primary trait, optional features]
# optional is SUPPORT_* = (trait, command)
MAPPING_COMPONENT = {
    group.DOMAIN: [TYPE_SCENE, TRAIT_SCENE, None],
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
        TYPE_LIGHT, TRAIT_ONOFF, {
            cover.SUPPORT_SET_POSITION: TRAIT_BRIGHTNESS
        }
    ],
    media_player.DOMAIN: [
        TYPE_LIGHT, TRAIT_ONOFF, {
            media_player.SUPPORT_VOLUME_SET: TRAIT_BRIGHTNESS
        }
    ],
    climate.DOMAIN: [TYPE_THERMOSTAT, TRAIT_TEMPERATURE_SETTING, None],
}  # type: Dict[str, list]


def make_actions_response(request_id: str, payload: dict) -> dict:
    """Make response message."""
    return {'requestId': request_id, 'payload': payload}


def entity_to_device(entity: Entity, units: UnitSystem):
    """Convert a hass entity into an google actions device."""
    class_data = MAPPING_COMPONENT.get(
        entity.attributes.get(ATTR_GOOGLE_ASSISTANT_TYPE) or entity.domain)
    if class_data is None:
        return None

    device = {
        'id': entity.entity_id,
        'name': {},
        'attributes': {},
        'traits': [],
        'willReportState': False,
    }
    device['type'] = class_data[0]
    device['traits'].append(class_data[1])

    # handle custom names
    device['name']['name'] = \
        entity.attributes.get(ATTR_GOOGLE_ASSISTANT_NAME) or \
        entity.attributes.get(CONF_FRIENDLY_NAME)

    # use aliases
    aliases = entity.attributes.get(CONF_ALIASES)
    if isinstance(aliases, list):
        device['name']['nicknames'] = aliases
    else:
        _LOGGER.warning("%s must be a list", CONF_ALIASES)

    # add trait if entity supports feature
    if class_data[2]:
        supported = entity.attributes.get(ATTR_SUPPORTED_FEATURES, 0)
        for feature, trait in class_data[2].items():
            if feature & supported > 0:
                device['traits'].append(trait)

                # Actions require this attributes for a device
                # supporting temperature
                # For IKEA trådfri, these attributes only seem to
                # be set only if the device is on?
                if trait == TRAIT_COLOR_TEMP:
                    if entity.attributes.get(
                            light.ATTR_MAX_MIREDS) is not None:
                        device['attributes']['temperatureMinK'] =  \
                            int(round(color.color_temperature_mired_to_kelvin(
                                entity.attributes.get(light.ATTR_MAX_MIREDS))))
                    if entity.attributes.get(
                            light.ATTR_MIN_MIREDS) is not None:
                        device['attributes']['temperatureMaxK'] =  \
                            int(round(color.color_temperature_mired_to_kelvin(
                                entity.attributes.get(light.ATTR_MIN_MIREDS))))

    if entity.domain == climate.DOMAIN:
        modes = ','.join(
            m for m in entity.attributes.get(climate.ATTR_OPERATION_LIST, [])
            if m in CLIMATE_SUPPORTED_MODES)
        device['attributes'] = {
            'availableThermostatModes': modes,
            'thermostatTemperatureUnit':
            'F' if units.temperature_unit == TEMP_FAHRENHEIT else 'C',
        }

    return device


def query_device(entity: Entity, units: UnitSystem) -> dict:
    """Take an entity and return a properly formatted device object."""
    def celsius(deg: Optional[float]) -> Optional[float]:
        """Convert a float to Celsius and rounds to one decimal place."""
        if deg is None:
            return None
        return round(METRIC_SYSTEM.temperature(deg, units.temperature_unit), 1)
    if entity.domain == climate.DOMAIN:
        mode = entity.attributes.get(climate.ATTR_OPERATION_MODE)
        if mode not in CLIMATE_SUPPORTED_MODES:
            mode = 'on'
        response = {
            'thermostatMode': mode,
            'thermostatTemperatureSetpoint':
            celsius(entity.attributes.get(climate.ATTR_TEMPERATURE)),
            'thermostatTemperatureAmbient':
            celsius(entity.attributes.get(climate.ATTR_CURRENT_TEMPERATURE)),
            'thermostatTemperatureSetpointHigh':
            celsius(entity.attributes.get(climate.ATTR_TARGET_TEMP_HIGH)),
            'thermostatTemperatureSetpointLow':
            celsius(entity.attributes.get(climate.ATTR_TARGET_TEMP_LOW)),
            'thermostatHumidityAmbient':
            entity.attributes.get(climate.ATTR_CURRENT_HUMIDITY),
        }
        return {k: v for k, v in response.items() if v is not None}

    final_state = entity.state != STATE_OFF
    final_brightness = entity.attributes.get(light.ATTR_BRIGHTNESS, 255
                                             if final_state else 0)

    if entity.domain == media_player.DOMAIN:
        level = entity.attributes.get(media_player.ATTR_MEDIA_VOLUME_LEVEL, 1.0
                                      if final_state else 0.0)
        # Convert 0.0-1.0 to 0-255
        final_brightness = round(min(1.0, level) * 255)

    if final_brightness is None:
        final_brightness = 255 if final_state else 0

    final_brightness = 100 * (final_brightness / 255)

    query_response = {
        "on": final_state,
        "online": True,
        "brightness": int(final_brightness)
    }

    supported_features = entity.attributes.get(ATTR_SUPPORTED_FEATURES, 0)
    if supported_features & \
       (light.SUPPORT_COLOR_TEMP | light.SUPPORT_RGB_COLOR):
        query_response["color"] = {}

        if entity.attributes.get(light.ATTR_COLOR_TEMP) is not None:
            query_response["color"]["temperature"] = \
                int(round(color.color_temperature_mired_to_kelvin(
                    entity.attributes.get(light.ATTR_COLOR_TEMP))))

        if entity.attributes.get(light.ATTR_COLOR_NAME) is not None:
            query_response["color"]["name"] = \
                entity.attributes.get(light.ATTR_COLOR_NAME)

        if entity.attributes.get(light.ATTR_RGB_COLOR) is not None:
            color_rgb = entity.attributes.get(light.ATTR_RGB_COLOR)
            if color_rgb is not None:
                query_response["color"]["spectrumRGB"] = \
                    int(color.color_rgb_to_hex(
                        color_rgb[0], color_rgb[1], color_rgb[2]), 16)

    return query_response


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
            service_data['temperature'] = units.temperature(
                params.get('thermostatTemperatureSetpoint', 25),
                TEMP_CELSIUS)
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
            service_data['operation_mode'] = params.get(
                'thermostatMode', 'off')
            return (climate.SERVICE_SET_OPERATION_MODE, service_data)

    if command == COMMAND_BRIGHTNESS:
        brightness = params.get('brightness')
        service_data['brightness'] = int(brightness / 100 * 255)
        return (SERVICE_TURN_ON, service_data)

    _LOGGER.debug("Handling command %s with data %s", command, params)
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
