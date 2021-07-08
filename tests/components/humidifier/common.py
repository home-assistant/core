"""Collection of helper methods.

All containing methods are legacy helpers that should not be used by new
components. Instead call the service directly.
"""
from homeassistant.components.humidifier import (
    ATTR_HUMIDITY,
    ATTR_MODE,
    DOMAIN,
    SERVICE_SET_HUMIDITY,
    SERVICE_SET_MODE,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ENTITY_MATCH_ALL,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)


async def async_turn_on(
    hass,
    entity_id=ENTITY_MATCH_ALL,
) -> None:
    """Turn all or specified humidifier on."""
    data = {
        key: value
        for key, value in [
            (ATTR_ENTITY_ID, entity_id),
        ]
        if value is not None
    }

    await hass.services.async_call(DOMAIN, SERVICE_TURN_ON, data, blocking=True)


async def async_turn_off(hass, entity_id=ENTITY_MATCH_ALL) -> None:
    """Turn all or specified humidier off."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}

    await hass.services.async_call(DOMAIN, SERVICE_TURN_OFF, data, blocking=True)


async def async_set_mode(
    hass, entity_id=ENTITY_MATCH_ALL, preset_mode: str = None
) -> None:
    """Set mode for all or specified humidifier."""
    data = {
        key: value
        for key, value in [(ATTR_ENTITY_ID, entity_id), (ATTR_MODE, preset_mode)]
        if value is not None
    }

    await hass.services.async_call(DOMAIN, SERVICE_SET_MODE, data, blocking=True)


async def async_set_humidity(
    hass, entity_id=ENTITY_MATCH_ALL, humidity: int = None
) -> None:
    """Set percentage for all or specified humidifier."""
    data = {
        key: value
        for key, value in [(ATTR_ENTITY_ID, entity_id), (ATTR_HUMIDITY, humidity)]
        if value is not None
    }

    await hass.services.async_call(DOMAIN, SERVICE_SET_HUMIDITY, data, blocking=True)
