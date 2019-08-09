"""Alexa message handlers."""
from datetime import datetime
import logging
import math

from homeassistant import core as ha
from homeassistant.components import cover, fan, group, light, media_player
from homeassistant.components.climate import const as climate
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    ATTR_TEMPERATURE,
    SERVICE_LOCK,
    SERVICE_MEDIA_NEXT_TRACK,
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_PREVIOUS_TRACK,
    SERVICE_MEDIA_STOP,
    SERVICE_SET_COVER_POSITION,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SERVICE_UNLOCK,
    SERVICE_VOLUME_DOWN,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_SET,
    SERVICE_VOLUME_UP,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
import homeassistant.util.color as color_util
from homeassistant.util.decorator import Registry
from homeassistant.util.temperature import convert as convert_temperature

from .const import API_TEMP_UNITS, API_THERMOSTAT_MODES, API_THERMOSTAT_PRESETS, Cause
from .entities import async_get_entities
from .errors import (
    AlexaInvalidValueError,
    AlexaTempRangeError,
    AlexaUnsupportedThermostatModeError,
)
from .state_report import async_enable_proactive_mode

_LOGGER = logging.getLogger(__name__)
HANDLERS = Registry()


@HANDLERS.register(("Alexa.Discovery", "Discover"))
async def async_api_discovery(hass, config, directive, context):
    """Create a API formatted discovery response.

    Async friendly.
    """
    discovery_endpoints = [
        alexa_entity.serialize_discovery()
        for alexa_entity in async_get_entities(hass, config)
        if config.should_expose(alexa_entity.entity_id)
    ]

    return directive.response(
        name="Discover.Response",
        namespace="Alexa.Discovery",
        payload={"endpoints": discovery_endpoints},
    )


@HANDLERS.register(("Alexa.Authorization", "AcceptGrant"))
async def async_api_accept_grant(hass, config, directive, context):
    """Create a API formatted AcceptGrant response.

    Async friendly.
    """
    auth_code = directive.payload["grant"]["code"]
    _LOGGER.debug("AcceptGrant code: %s", auth_code)

    if config.supports_auth:
        await config.async_accept_grant(auth_code)

        if config.should_report_state:
            await async_enable_proactive_mode(hass, config)

    return directive.response(
        name="AcceptGrant.Response", namespace="Alexa.Authorization", payload={}
    )


@HANDLERS.register(("Alexa.PowerController", "TurnOn"))
async def async_api_turn_on(hass, config, directive, context):
    """Process a turn on request."""
    entity = directive.entity
    domain = entity.domain
    if domain == group.DOMAIN:
        domain = ha.DOMAIN

    service = SERVICE_TURN_ON
    if domain == cover.DOMAIN:
        service = cover.SERVICE_OPEN_COVER
    elif domain == media_player.DOMAIN:
        supported = entity.attributes.get(ATTR_SUPPORTED_FEATURES, 0)
        power_features = media_player.SUPPORT_TURN_ON | media_player.SUPPORT_TURN_OFF
        if not supported & power_features:
            service = media_player.SERVICE_MEDIA_PLAY

    await hass.services.async_call(
        domain,
        service,
        {ATTR_ENTITY_ID: entity.entity_id},
        blocking=False,
        context=context,
    )

    return directive.response()


@HANDLERS.register(("Alexa.PowerController", "TurnOff"))
async def async_api_turn_off(hass, config, directive, context):
    """Process a turn off request."""
    entity = directive.entity
    domain = entity.domain
    if entity.domain == group.DOMAIN:
        domain = ha.DOMAIN

    service = SERVICE_TURN_OFF
    if entity.domain == cover.DOMAIN:
        service = cover.SERVICE_CLOSE_COVER
    elif domain == media_player.DOMAIN:
        supported = entity.attributes.get(ATTR_SUPPORTED_FEATURES, 0)
        power_features = media_player.SUPPORT_TURN_ON | media_player.SUPPORT_TURN_OFF
        if not supported & power_features:
            service = media_player.SERVICE_MEDIA_STOP

    await hass.services.async_call(
        domain,
        service,
        {ATTR_ENTITY_ID: entity.entity_id},
        blocking=False,
        context=context,
    )

    return directive.response()


@HANDLERS.register(("Alexa.BrightnessController", "SetBrightness"))
async def async_api_set_brightness(hass, config, directive, context):
    """Process a set brightness request."""
    entity = directive.entity
    brightness = int(directive.payload["brightness"])

    await hass.services.async_call(
        entity.domain,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity.entity_id, light.ATTR_BRIGHTNESS_PCT: brightness},
        blocking=False,
        context=context,
    )

    return directive.response()


@HANDLERS.register(("Alexa.BrightnessController", "AdjustBrightness"))
async def async_api_adjust_brightness(hass, config, directive, context):
    """Process an adjust brightness request."""
    entity = directive.entity
    brightness_delta = int(directive.payload["brightnessDelta"])

    # read current state
    try:
        current = math.floor(
            int(entity.attributes.get(light.ATTR_BRIGHTNESS)) / 255 * 100
        )
    except ZeroDivisionError:
        current = 0

    # set brightness
    brightness = max(0, brightness_delta + current)
    await hass.services.async_call(
        entity.domain,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity.entity_id, light.ATTR_BRIGHTNESS_PCT: brightness},
        blocking=False,
        context=context,
    )

    return directive.response()


@HANDLERS.register(("Alexa.ColorController", "SetColor"))
async def async_api_set_color(hass, config, directive, context):
    """Process a set color request."""
    entity = directive.entity
    rgb = color_util.color_hsb_to_RGB(
        float(directive.payload["color"]["hue"]),
        float(directive.payload["color"]["saturation"]),
        float(directive.payload["color"]["brightness"]),
    )

    await hass.services.async_call(
        entity.domain,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity.entity_id, light.ATTR_RGB_COLOR: rgb},
        blocking=False,
        context=context,
    )

    return directive.response()


@HANDLERS.register(("Alexa.ColorTemperatureController", "SetColorTemperature"))
async def async_api_set_color_temperature(hass, config, directive, context):
    """Process a set color temperature request."""
    entity = directive.entity
    kelvin = int(directive.payload["colorTemperatureInKelvin"])

    await hass.services.async_call(
        entity.domain,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity.entity_id, light.ATTR_KELVIN: kelvin},
        blocking=False,
        context=context,
    )

    return directive.response()


@HANDLERS.register(("Alexa.ColorTemperatureController", "DecreaseColorTemperature"))
async def async_api_decrease_color_temp(hass, config, directive, context):
    """Process a decrease color temperature request."""
    entity = directive.entity
    current = int(entity.attributes.get(light.ATTR_COLOR_TEMP))
    max_mireds = int(entity.attributes.get(light.ATTR_MAX_MIREDS))

    value = min(max_mireds, current + 50)
    await hass.services.async_call(
        entity.domain,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity.entity_id, light.ATTR_COLOR_TEMP: value},
        blocking=False,
        context=context,
    )

    return directive.response()


@HANDLERS.register(("Alexa.ColorTemperatureController", "IncreaseColorTemperature"))
async def async_api_increase_color_temp(hass, config, directive, context):
    """Process an increase color temperature request."""
    entity = directive.entity
    current = int(entity.attributes.get(light.ATTR_COLOR_TEMP))
    min_mireds = int(entity.attributes.get(light.ATTR_MIN_MIREDS))

    value = max(min_mireds, current - 50)
    await hass.services.async_call(
        entity.domain,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity.entity_id, light.ATTR_COLOR_TEMP: value},
        blocking=False,
        context=context,
    )

    return directive.response()


@HANDLERS.register(("Alexa.SceneController", "Activate"))
async def async_api_activate(hass, config, directive, context):
    """Process an activate request."""
    entity = directive.entity
    domain = entity.domain

    await hass.services.async_call(
        domain,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity.entity_id},
        blocking=False,
        context=context,
    )

    payload = {
        "cause": {"type": Cause.VOICE_INTERACTION},
        "timestamp": "%sZ" % (datetime.utcnow().isoformat(),),
    }

    return directive.response(
        name="ActivationStarted", namespace="Alexa.SceneController", payload=payload
    )


@HANDLERS.register(("Alexa.SceneController", "Deactivate"))
async def async_api_deactivate(hass, config, directive, context):
    """Process a deactivate request."""
    entity = directive.entity
    domain = entity.domain

    await hass.services.async_call(
        domain,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity.entity_id},
        blocking=False,
        context=context,
    )

    payload = {
        "cause": {"type": Cause.VOICE_INTERACTION},
        "timestamp": "%sZ" % (datetime.utcnow().isoformat(),),
    }

    return directive.response(
        name="DeactivationStarted", namespace="Alexa.SceneController", payload=payload
    )


@HANDLERS.register(("Alexa.PercentageController", "SetPercentage"))
async def async_api_set_percentage(hass, config, directive, context):
    """Process a set percentage request."""
    entity = directive.entity
    percentage = int(directive.payload["percentage"])
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
        entity.domain, service, data, blocking=False, context=context
    )

    return directive.response()


@HANDLERS.register(("Alexa.PercentageController", "AdjustPercentage"))
async def async_api_adjust_percentage(hass, config, directive, context):
    """Process an adjust percentage request."""
    entity = directive.entity
    percentage_delta = int(directive.payload["percentageDelta"])
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
        entity.domain, service, data, blocking=False, context=context
    )

    return directive.response()


@HANDLERS.register(("Alexa.LockController", "Lock"))
async def async_api_lock(hass, config, directive, context):
    """Process a lock request."""
    entity = directive.entity
    await hass.services.async_call(
        entity.domain,
        SERVICE_LOCK,
        {ATTR_ENTITY_ID: entity.entity_id},
        blocking=False,
        context=context,
    )

    response = directive.response()
    response.add_context_property(
        {"name": "lockState", "namespace": "Alexa.LockController", "value": "LOCKED"}
    )
    return response


# Not supported by Alexa yet
@HANDLERS.register(("Alexa.LockController", "Unlock"))
async def async_api_unlock(hass, config, directive, context):
    """Process an unlock request."""
    entity = directive.entity
    await hass.services.async_call(
        entity.domain,
        SERVICE_UNLOCK,
        {ATTR_ENTITY_ID: entity.entity_id},
        blocking=False,
        context=context,
    )

    return directive.response()


@HANDLERS.register(("Alexa.Speaker", "SetVolume"))
async def async_api_set_volume(hass, config, directive, context):
    """Process a set volume request."""
    volume = round(float(directive.payload["volume"] / 100), 2)
    entity = directive.entity

    data = {
        ATTR_ENTITY_ID: entity.entity_id,
        media_player.const.ATTR_MEDIA_VOLUME_LEVEL: volume,
    }

    await hass.services.async_call(
        entity.domain, SERVICE_VOLUME_SET, data, blocking=False, context=context
    )

    return directive.response()


@HANDLERS.register(("Alexa.InputController", "SelectInput"))
async def async_api_select_input(hass, config, directive, context):
    """Process a set input request."""
    media_input = directive.payload["input"]
    entity = directive.entity

    # attempt to map the ALL UPPERCASE payload name to a source
    source_list = entity.attributes[media_player.const.ATTR_INPUT_SOURCE_LIST] or []
    for source in source_list:
        # response will always be space separated, so format the source in the
        # most likely way to find a match
        formatted_source = source.lower().replace("-", " ").replace("_", " ")
        if formatted_source in media_input.lower():
            media_input = source
            break
    else:
        msg = "failed to map input {} to a media source on {}".format(
            media_input, entity.entity_id
        )
        raise AlexaInvalidValueError(msg)

    data = {
        ATTR_ENTITY_ID: entity.entity_id,
        media_player.const.ATTR_INPUT_SOURCE: media_input,
    }

    await hass.services.async_call(
        entity.domain,
        media_player.SERVICE_SELECT_SOURCE,
        data,
        blocking=False,
        context=context,
    )

    return directive.response()


@HANDLERS.register(("Alexa.Speaker", "AdjustVolume"))
async def async_api_adjust_volume(hass, config, directive, context):
    """Process an adjust volume request."""
    volume_delta = int(directive.payload["volume"])

    entity = directive.entity
    current_level = entity.attributes.get(media_player.const.ATTR_MEDIA_VOLUME_LEVEL)

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
        entity.domain, SERVICE_VOLUME_SET, data, blocking=False, context=context
    )

    return directive.response()


@HANDLERS.register(("Alexa.StepSpeaker", "AdjustVolume"))
async def async_api_adjust_volume_step(hass, config, directive, context):
    """Process an adjust volume step request."""
    # media_player volume up/down service does not support specifying steps
    # each component handles it differently e.g. via config.
    # For now we use the volumeSteps returned to figure out if we
    # should step up/down
    volume_step = directive.payload["volumeSteps"]
    entity = directive.entity

    data = {ATTR_ENTITY_ID: entity.entity_id}

    if volume_step > 0:
        await hass.services.async_call(
            entity.domain, SERVICE_VOLUME_UP, data, blocking=False, context=context
        )
    elif volume_step < 0:
        await hass.services.async_call(
            entity.domain, SERVICE_VOLUME_DOWN, data, blocking=False, context=context
        )

    return directive.response()


@HANDLERS.register(("Alexa.StepSpeaker", "SetMute"))
@HANDLERS.register(("Alexa.Speaker", "SetMute"))
async def async_api_set_mute(hass, config, directive, context):
    """Process a set mute request."""
    mute = bool(directive.payload["mute"])
    entity = directive.entity

    data = {
        ATTR_ENTITY_ID: entity.entity_id,
        media_player.const.ATTR_MEDIA_VOLUME_MUTED: mute,
    }

    await hass.services.async_call(
        entity.domain, SERVICE_VOLUME_MUTE, data, blocking=False, context=context
    )

    return directive.response()


@HANDLERS.register(("Alexa.PlaybackController", "Play"))
async def async_api_play(hass, config, directive, context):
    """Process a play request."""
    entity = directive.entity
    data = {ATTR_ENTITY_ID: entity.entity_id}

    await hass.services.async_call(
        entity.domain, SERVICE_MEDIA_PLAY, data, blocking=False, context=context
    )

    return directive.response()


@HANDLERS.register(("Alexa.PlaybackController", "Pause"))
async def async_api_pause(hass, config, directive, context):
    """Process a pause request."""
    entity = directive.entity
    data = {ATTR_ENTITY_ID: entity.entity_id}

    await hass.services.async_call(
        entity.domain, SERVICE_MEDIA_PAUSE, data, blocking=False, context=context
    )

    return directive.response()


@HANDLERS.register(("Alexa.PlaybackController", "Stop"))
async def async_api_stop(hass, config, directive, context):
    """Process a stop request."""
    entity = directive.entity
    data = {ATTR_ENTITY_ID: entity.entity_id}

    await hass.services.async_call(
        entity.domain, SERVICE_MEDIA_STOP, data, blocking=False, context=context
    )

    return directive.response()


@HANDLERS.register(("Alexa.PlaybackController", "Next"))
async def async_api_next(hass, config, directive, context):
    """Process a next request."""
    entity = directive.entity
    data = {ATTR_ENTITY_ID: entity.entity_id}

    await hass.services.async_call(
        entity.domain, SERVICE_MEDIA_NEXT_TRACK, data, blocking=False, context=context
    )

    return directive.response()


@HANDLERS.register(("Alexa.PlaybackController", "Previous"))
async def async_api_previous(hass, config, directive, context):
    """Process a previous request."""
    entity = directive.entity
    data = {ATTR_ENTITY_ID: entity.entity_id}

    await hass.services.async_call(
        entity.domain,
        SERVICE_MEDIA_PREVIOUS_TRACK,
        data,
        blocking=False,
        context=context,
    )

    return directive.response()


def temperature_from_object(hass, temp_obj, interval=False):
    """Get temperature from Temperature object in requested unit."""
    to_unit = hass.config.units.temperature_unit
    from_unit = TEMP_CELSIUS
    temp = float(temp_obj["value"])

    if temp_obj["scale"] == "FAHRENHEIT":
        from_unit = TEMP_FAHRENHEIT
    elif temp_obj["scale"] == "KELVIN":
        # convert to Celsius if absolute temperature
        if not interval:
            temp -= 273.15

    return convert_temperature(temp, from_unit, to_unit, interval)


@HANDLERS.register(("Alexa.ThermostatController", "SetTargetTemperature"))
async def async_api_set_target_temp(hass, config, directive, context):
    """Process a set target temperature request."""
    entity = directive.entity
    min_temp = entity.attributes.get(climate.ATTR_MIN_TEMP)
    max_temp = entity.attributes.get(climate.ATTR_MAX_TEMP)
    unit = hass.config.units.temperature_unit

    data = {ATTR_ENTITY_ID: entity.entity_id}

    payload = directive.payload
    response = directive.response()
    if "targetSetpoint" in payload:
        temp = temperature_from_object(hass, payload["targetSetpoint"])
        if temp < min_temp or temp > max_temp:
            raise AlexaTempRangeError(hass, temp, min_temp, max_temp)
        data[ATTR_TEMPERATURE] = temp
        response.add_context_property(
            {
                "name": "targetSetpoint",
                "namespace": "Alexa.ThermostatController",
                "value": {"value": temp, "scale": API_TEMP_UNITS[unit]},
            }
        )
    if "lowerSetpoint" in payload:
        temp_low = temperature_from_object(hass, payload["lowerSetpoint"])
        if temp_low < min_temp or temp_low > max_temp:
            raise AlexaTempRangeError(hass, temp_low, min_temp, max_temp)
        data[climate.ATTR_TARGET_TEMP_LOW] = temp_low
        response.add_context_property(
            {
                "name": "lowerSetpoint",
                "namespace": "Alexa.ThermostatController",
                "value": {"value": temp_low, "scale": API_TEMP_UNITS[unit]},
            }
        )
    if "upperSetpoint" in payload:
        temp_high = temperature_from_object(hass, payload["upperSetpoint"])
        if temp_high < min_temp or temp_high > max_temp:
            raise AlexaTempRangeError(hass, temp_high, min_temp, max_temp)
        data[climate.ATTR_TARGET_TEMP_HIGH] = temp_high
        response.add_context_property(
            {
                "name": "upperSetpoint",
                "namespace": "Alexa.ThermostatController",
                "value": {"value": temp_high, "scale": API_TEMP_UNITS[unit]},
            }
        )

    await hass.services.async_call(
        entity.domain,
        climate.SERVICE_SET_TEMPERATURE,
        data,
        blocking=False,
        context=context,
    )

    return response


@HANDLERS.register(("Alexa.ThermostatController", "AdjustTargetTemperature"))
async def async_api_adjust_target_temp(hass, config, directive, context):
    """Process an adjust target temperature request."""
    entity = directive.entity
    min_temp = entity.attributes.get(climate.ATTR_MIN_TEMP)
    max_temp = entity.attributes.get(climate.ATTR_MAX_TEMP)
    unit = hass.config.units.temperature_unit

    temp_delta = temperature_from_object(
        hass, directive.payload["targetSetpointDelta"], interval=True
    )
    target_temp = float(entity.attributes.get(ATTR_TEMPERATURE)) + temp_delta

    if target_temp < min_temp or target_temp > max_temp:
        raise AlexaTempRangeError(hass, target_temp, min_temp, max_temp)

    data = {ATTR_ENTITY_ID: entity.entity_id, ATTR_TEMPERATURE: target_temp}

    response = directive.response()
    await hass.services.async_call(
        entity.domain,
        climate.SERVICE_SET_TEMPERATURE,
        data,
        blocking=False,
        context=context,
    )
    response.add_context_property(
        {
            "name": "targetSetpoint",
            "namespace": "Alexa.ThermostatController",
            "value": {"value": target_temp, "scale": API_TEMP_UNITS[unit]},
        }
    )

    return response


@HANDLERS.register(("Alexa.ThermostatController", "SetThermostatMode"))
async def async_api_set_thermostat_mode(hass, config, directive, context):
    """Process a set thermostat mode request."""
    entity = directive.entity
    mode = directive.payload["thermostatMode"]
    mode = mode if isinstance(mode, str) else mode["value"]

    data = {ATTR_ENTITY_ID: entity.entity_id}

    ha_preset = next((k for k, v in API_THERMOSTAT_PRESETS.items() if v == mode), None)

    if ha_preset:
        presets = entity.attributes.get(climate.ATTR_PRESET_MODES, [])

        if ha_preset not in presets:
            msg = "The requested thermostat mode {} is not supported".format(ha_preset)
            raise AlexaUnsupportedThermostatModeError(msg)

        service = climate.SERVICE_SET_PRESET_MODE
        data[climate.ATTR_PRESET_MODE] = climate.PRESET_ECO

    else:
        operation_list = entity.attributes.get(climate.ATTR_HVAC_MODES)
        ha_mode = next((k for k, v in API_THERMOSTAT_MODES.items() if v == mode), None)
        if ha_mode not in operation_list:
            msg = "The requested thermostat mode {} is not supported".format(mode)
            raise AlexaUnsupportedThermostatModeError(msg)

        service = climate.SERVICE_SET_HVAC_MODE
        data[climate.ATTR_HVAC_MODE] = ha_mode

    response = directive.response()
    await hass.services.async_call(
        climate.DOMAIN, service, data, blocking=False, context=context
    )
    response.add_context_property(
        {
            "name": "thermostatMode",
            "namespace": "Alexa.ThermostatController",
            "value": mode,
        }
    )

    return response


@HANDLERS.register(("Alexa", "ReportState"))
async def async_api_reportstate(hass, config, directive, context):
    """Process a ReportState request."""
    return directive.response(name="StateReport")
