"""Collection of helper methods.

All containing methods are legacy helpers that should not be used by new
components. Instead call the service directly.
"""
from homeassistant.components.water_heater import (
    _LOGGER, ATTR_AWAY_MODE,
    ATTR_OPERATION_MODE, DOMAIN, SERVICE_SET_AWAY_MODE,
    SERVICE_SET_TEMPERATURE, SERVICE_SET_OPERATION_MODE)
from homeassistant.const import (
    ATTR_ENTITY_ID, ATTR_TEMPERATURE)
from homeassistant.loader import bind_hass


@bind_hass
def set_away_mode(hass, away_mode, entity_id=None):
    """Turn all or specified water_heater devices away mode on."""
    data = {
        ATTR_AWAY_MODE: away_mode
    }

    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    hass.services.call(DOMAIN, SERVICE_SET_AWAY_MODE, data)


@bind_hass
def set_temperature(hass, temperature=None, entity_id=None,
                    operation_mode=None):
    """Set new target temperature."""
    kwargs = {
        key: value for key, value in [
            (ATTR_TEMPERATURE, temperature),
            (ATTR_ENTITY_ID, entity_id),
            (ATTR_OPERATION_MODE, operation_mode)
        ] if value is not None
    }
    _LOGGER.debug("set_temperature start data=%s", kwargs)
    hass.services.call(DOMAIN, SERVICE_SET_TEMPERATURE, kwargs)


@bind_hass
def set_operation_mode(hass, operation_mode, entity_id=None):
    """Set new target operation mode."""
    data = {ATTR_OPERATION_MODE: operation_mode}

    if entity_id is not None:
        data[ATTR_ENTITY_ID] = entity_id

    hass.services.call(DOMAIN, SERVICE_SET_OPERATION_MODE, data)
