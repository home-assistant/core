"""Collection of helper methods.

All containing methods are legacy helpers that should not be used by new
components. Instead call the service directly.
"""
from homeassistant.components.climate import (
    _LOGGER,
    ATTR_AUX_HEAT,
    ATTR_FAN_MODE,
    ATTR_HUMIDITY,
    ATTR_HVAC_MODE,
    ATTR_PRESET_MODE,
    ATTR_SWING_MODE,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    DOMAIN,
    SERVICE_SET_AUX_HEAT,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HUMIDITY,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_SWING_MODE,
    SERVICE_SET_TEMPERATURE,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    ENTITY_MATCH_ALL,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.loader import bind_hass


async def async_set_preset_mode(hass, preset_mode, entity_id=ENTITY_MATCH_ALL):
    """Set new preset mode."""
    data = {ATTR_PRESET_MODE: preset_mode}

    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    await hass.services.async_call(DOMAIN, SERVICE_SET_PRESET_MODE, data, blocking=True)


@bind_hass
def set_preset_mode(hass, preset_mode, entity_id=ENTITY_MATCH_ALL):
    """Set new preset mode."""
    data = {ATTR_PRESET_MODE: preset_mode}

    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    hass.services.call(DOMAIN, SERVICE_SET_PRESET_MODE, data)


async def async_set_aux_heat(hass, aux_heat, entity_id=ENTITY_MATCH_ALL):
    """Turn all or specified climate devices auxiliary heater on."""
    data = {ATTR_AUX_HEAT: aux_heat}

    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    await hass.services.async_call(DOMAIN, SERVICE_SET_AUX_HEAT, data, blocking=True)


@bind_hass
def set_aux_heat(hass, aux_heat, entity_id=ENTITY_MATCH_ALL):
    """Turn all or specified climate devices auxiliary heater on."""
    data = {ATTR_AUX_HEAT: aux_heat}

    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    hass.services.call(DOMAIN, SERVICE_SET_AUX_HEAT, data)


async def async_set_temperature(
    hass,
    temperature=None,
    entity_id=ENTITY_MATCH_ALL,
    target_temp_high=None,
    target_temp_low=None,
    hvac_mode=None,
):
    """Set new target temperature."""
    kwargs = {
        key: value
        for key, value in [
            (ATTR_TEMPERATURE, temperature),
            (ATTR_TARGET_TEMP_HIGH, target_temp_high),
            (ATTR_TARGET_TEMP_LOW, target_temp_low),
            (ATTR_ENTITY_ID, entity_id),
            (ATTR_HVAC_MODE, hvac_mode),
        ]
        if value is not None
    }
    _LOGGER.debug("set_temperature start data=%s", kwargs)
    await hass.services.async_call(
        DOMAIN, SERVICE_SET_TEMPERATURE, kwargs, blocking=True
    )


@bind_hass
def set_temperature(
    hass,
    temperature=None,
    entity_id=ENTITY_MATCH_ALL,
    target_temp_high=None,
    target_temp_low=None,
    hvac_mode=None,
):
    """Set new target temperature."""
    kwargs = {
        key: value
        for key, value in [
            (ATTR_TEMPERATURE, temperature),
            (ATTR_TARGET_TEMP_HIGH, target_temp_high),
            (ATTR_TARGET_TEMP_LOW, target_temp_low),
            (ATTR_ENTITY_ID, entity_id),
            (ATTR_HVAC_MODE, hvac_mode),
        ]
        if value is not None
    }
    _LOGGER.debug("set_temperature start data=%s", kwargs)
    hass.services.call(DOMAIN, SERVICE_SET_TEMPERATURE, kwargs)


async def async_set_humidity(hass, humidity, entity_id=ENTITY_MATCH_ALL):
    """Set new target humidity."""
    data = {ATTR_HUMIDITY: humidity}

    if entity_id is not None:
        data[ATTR_ENTITY_ID] = entity_id

    await hass.services.async_call(DOMAIN, SERVICE_SET_HUMIDITY, data, blocking=True)


@bind_hass
def set_humidity(hass, humidity, entity_id=ENTITY_MATCH_ALL):
    """Set new target humidity."""
    data = {ATTR_HUMIDITY: humidity}

    if entity_id is not None:
        data[ATTR_ENTITY_ID] = entity_id

    hass.services.call(DOMAIN, SERVICE_SET_HUMIDITY, data)


async def async_set_fan_mode(hass, fan, entity_id=ENTITY_MATCH_ALL):
    """Set all or specified climate devices fan mode on."""
    data = {ATTR_FAN_MODE: fan}

    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    await hass.services.async_call(DOMAIN, SERVICE_SET_FAN_MODE, data, blocking=True)


@bind_hass
def set_fan_mode(hass, fan, entity_id=ENTITY_MATCH_ALL):
    """Set all or specified climate devices fan mode on."""
    data = {ATTR_FAN_MODE: fan}

    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    hass.services.call(DOMAIN, SERVICE_SET_FAN_MODE, data)


async def async_set_hvac_mode(hass, hvac_mode, entity_id=ENTITY_MATCH_ALL):
    """Set new target operation mode."""
    data = {ATTR_HVAC_MODE: hvac_mode}

    if entity_id is not None:
        data[ATTR_ENTITY_ID] = entity_id

    await hass.services.async_call(DOMAIN, SERVICE_SET_HVAC_MODE, data, blocking=True)


@bind_hass
def set_operation_mode(hass, hvac_mode, entity_id=ENTITY_MATCH_ALL):
    """Set new target operation mode."""
    data = {ATTR_HVAC_MODE: hvac_mode}

    if entity_id is not None:
        data[ATTR_ENTITY_ID] = entity_id

    hass.services.call(DOMAIN, SERVICE_SET_HVAC_MODE, data)


async def async_set_swing_mode(hass, swing_mode, entity_id=ENTITY_MATCH_ALL):
    """Set new target swing mode."""
    data = {ATTR_SWING_MODE: swing_mode}

    if entity_id is not None:
        data[ATTR_ENTITY_ID] = entity_id

    await hass.services.async_call(DOMAIN, SERVICE_SET_SWING_MODE, data, blocking=True)


@bind_hass
def set_swing_mode(hass, swing_mode, entity_id=ENTITY_MATCH_ALL):
    """Set new target swing mode."""
    data = {ATTR_SWING_MODE: swing_mode}

    if entity_id is not None:
        data[ATTR_ENTITY_ID] = entity_id

    hass.services.call(DOMAIN, SERVICE_SET_SWING_MODE, data)


async def async_turn_on(hass, entity_id=ENTITY_MATCH_ALL):
    """Turn on device."""
    data = {}

    if entity_id is not None:
        data[ATTR_ENTITY_ID] = entity_id

    await hass.services.async_call(DOMAIN, SERVICE_TURN_ON, data, blocking=True)


async def async_turn_off(hass, entity_id=ENTITY_MATCH_ALL):
    """Turn off device."""
    data = {}

    if entity_id is not None:
        data[ATTR_ENTITY_ID] = entity_id

    await hass.services.async_call(DOMAIN, SERVICE_TURN_OFF, data, blocking=True)
