"""Collection of helper methods.

All containing methods are legacy helpers that should not be used by new
components. Instead call the service directly.
"""
from homeassistant.components.climate import (
    _LOGGER, ATTR_AUX_HEAT, ATTR_AWAY_MODE, ATTR_FAN_MODE, ATTR_HOLD_MODE,
    ATTR_HUMIDITY, ATTR_OPERATION_MODE, ATTR_SWING_MODE, ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW, DOMAIN, SERVICE_SET_AWAY_MODE, SERVICE_SET_HOLD_MODE,
    SERVICE_SET_AUX_HEAT, SERVICE_SET_TEMPERATURE, SERVICE_SET_HUMIDITY,
    SERVICE_SET_FAN_MODE, SERVICE_SET_OPERATION_MODE, SERVICE_SET_SWING_MODE)
from homeassistant.const import (
    ATTR_ENTITY_ID, ATTR_TEMPERATURE)
from homeassistant.loader import bind_hass


@bind_hass
def set_away_mode(hass, away_mode, entity_id=None):
    """Turn all or specified climate devices away mode on."""
    data = {
        ATTR_AWAY_MODE: away_mode
    }

    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    hass.services.call(DOMAIN, SERVICE_SET_AWAY_MODE, data)


@bind_hass
def set_hold_mode(hass, hold_mode, entity_id=None):
    """Set new hold mode."""
    data = {
        ATTR_HOLD_MODE: hold_mode
    }

    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    hass.services.call(DOMAIN, SERVICE_SET_HOLD_MODE, data)


@bind_hass
def set_aux_heat(hass, aux_heat, entity_id=None):
    """Turn all or specified climate devices auxiliary heater on."""
    data = {
        ATTR_AUX_HEAT: aux_heat
    }

    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    hass.services.call(DOMAIN, SERVICE_SET_AUX_HEAT, data)


@bind_hass
def set_temperature(hass, temperature=None, entity_id=None,
                    target_temp_high=None, target_temp_low=None,
                    operation_mode=None):
    """Set new target temperature."""
    kwargs = {
        key: value for key, value in [
            (ATTR_TEMPERATURE, temperature),
            (ATTR_TARGET_TEMP_HIGH, target_temp_high),
            (ATTR_TARGET_TEMP_LOW, target_temp_low),
            (ATTR_ENTITY_ID, entity_id),
            (ATTR_OPERATION_MODE, operation_mode)
        ] if value is not None
    }
    _LOGGER.debug("set_temperature start data=%s", kwargs)
    hass.services.call(DOMAIN, SERVICE_SET_TEMPERATURE, kwargs)


@bind_hass
def set_humidity(hass, humidity, entity_id=None):
    """Set new target humidity."""
    data = {ATTR_HUMIDITY: humidity}

    if entity_id is not None:
        data[ATTR_ENTITY_ID] = entity_id

    hass.services.call(DOMAIN, SERVICE_SET_HUMIDITY, data)


@bind_hass
def set_fan_mode(hass, fan, entity_id=None):
    """Set all or specified climate devices fan mode on."""
    data = {ATTR_FAN_MODE: fan}

    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    hass.services.call(DOMAIN, SERVICE_SET_FAN_MODE, data)


@bind_hass
def set_operation_mode(hass, operation_mode, entity_id=None):
    """Set new target operation mode."""
    data = {ATTR_OPERATION_MODE: operation_mode}

    if entity_id is not None:
        data[ATTR_ENTITY_ID] = entity_id

    hass.services.call(DOMAIN, SERVICE_SET_OPERATION_MODE, data)


@bind_hass
def set_swing_mode(hass, swing_mode, entity_id=None):
    """Set new target swing mode."""
    data = {ATTR_SWING_MODE: swing_mode}

    if entity_id is not None:
        data[ATTR_ENTITY_ID] = entity_id

    hass.services.call(DOMAIN, SERVICE_SET_SWING_MODE, data)
