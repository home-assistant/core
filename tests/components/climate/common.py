"""Collection of helper methods.

All containing methods are legacy helpers that should not be used by new
components. Instead call the service directly.
"""

from homeassistant.components.climate import (
    _LOGGER,
    DOMAIN,
    ClimateService,
    ClimateServiceArgument,
    HVACMode,
)
from homeassistant.const import ENTITY_MATCH_ALL, TargetKey
from homeassistant.core import HomeAssistant


async def async_set_preset_mode(
    hass: HomeAssistant, preset_mode: str, entity_id: str = ENTITY_MATCH_ALL
) -> None:
    """Set new preset mode."""
    data = {ClimateServiceArgument.PRESET_MODE: preset_mode}

    if entity_id:
        data[TargetKey.ENTITY_ID] = entity_id

    await hass.services.async_call(
        DOMAIN, ClimateService.SET_PRESET_MODE, data, blocking=True
    )


def set_preset_mode(
    hass: HomeAssistant, preset_mode: str, entity_id: str = ENTITY_MATCH_ALL
) -> None:
    """Set new preset mode."""
    data = {ClimateServiceArgument.PRESET_MODE: preset_mode}

    if entity_id:
        data[TargetKey.ENTITY_ID] = entity_id

    hass.services.call(DOMAIN, ClimateService.SET_PRESET_MODE, data)


async def async_set_temperature(
    hass: HomeAssistant,
    temperature: float | None = None,
    entity_id: str = ENTITY_MATCH_ALL,
    target_temp_high: float | None = None,
    target_temp_low: float | None = None,
    hvac_mode: HVACMode | None = None,
) -> None:
    """Set new target temperature."""
    kwargs = {
        key: value
        for key, value in (
            (ClimateServiceArgument.TEMPERATURE, temperature),
            (ClimateServiceArgument.TARGET_TEMP_HIGH, target_temp_high),
            (ClimateServiceArgument.TARGET_TEMP_LOW, target_temp_low),
            (TargetKey.ENTITY_ID, entity_id),
            (ClimateServiceArgument.HVAC_MODE, hvac_mode),
        )
        if value is not None
    }
    _LOGGER.debug("set_temperature start data=%s", kwargs)
    await hass.services.async_call(
        DOMAIN, ClimateService.SET_TEMPERATURE, kwargs, blocking=True
    )


def set_temperature(
    hass: HomeAssistant,
    temperature: float | None = None,
    entity_id: str = ENTITY_MATCH_ALL,
    target_temp_high: float | None = None,
    target_temp_low: float | None = None,
    hvac_mode: HVACMode | None = None,
) -> None:
    """Set new target temperature."""
    kwargs = {
        key: value
        for key, value in (
            (ClimateServiceArgument.TEMPERATURE, temperature),
            (ClimateServiceArgument.TARGET_TEMP_HIGH, target_temp_high),
            (ClimateServiceArgument.TARGET_TEMP_LOW, target_temp_low),
            (TargetKey.ENTITY_ID, entity_id),
            (ClimateServiceArgument.HVAC_MODE, hvac_mode),
        )
        if value is not None
    }
    _LOGGER.debug("set_temperature start data=%s", kwargs)
    hass.services.call(DOMAIN, ClimateService.SET_TEMPERATURE, kwargs)


async def async_set_humidity(
    hass: HomeAssistant, humidity: int, entity_id: str = ENTITY_MATCH_ALL
) -> None:
    """Set new target humidity."""
    data = {ClimateServiceArgument.HUMIDITY: humidity}

    if entity_id is not None:
        data[TargetKey.ENTITY_ID] = entity_id

    await hass.services.async_call(
        DOMAIN, ClimateService.SET_HUMIDITY, data, blocking=True
    )


def set_humidity(
    hass: HomeAssistant, humidity: int, entity_id: str = ENTITY_MATCH_ALL
) -> None:
    """Set new target humidity."""
    data = {ClimateServiceArgument.HUMIDITY: humidity}

    if entity_id is not None:
        data[TargetKey.ENTITY_ID] = entity_id

    hass.services.call(DOMAIN, ClimateService.SET_HUMIDITY, data)


async def async_set_fan_mode(
    hass: HomeAssistant, fan: str, entity_id: str = ENTITY_MATCH_ALL
) -> None:
    """Set all or specified climate devices fan mode on."""
    data = {ClimateServiceArgument.FAN_MODE: fan}

    if entity_id:
        data[TargetKey.ENTITY_ID] = entity_id

    await hass.services.async_call(
        DOMAIN, ClimateService.SET_FAN_MODE, data, blocking=True
    )


def set_fan_mode(
    hass: HomeAssistant, fan: str, entity_id: str = ENTITY_MATCH_ALL
) -> None:
    """Set all or specified climate devices fan mode on."""
    data = {ClimateServiceArgument.FAN_MODE: fan}

    if entity_id:
        data[TargetKey.ENTITY_ID] = entity_id

    hass.services.call(DOMAIN, ClimateService.SET_FAN_MODE, data)


async def async_set_hvac_mode(
    hass: HomeAssistant, hvac_mode: HVACMode, entity_id: str = ENTITY_MATCH_ALL
) -> None:
    """Set new target operation mode."""
    data = {ClimateServiceArgument.HVAC_MODE: hvac_mode}

    if entity_id is not None:
        data[TargetKey.ENTITY_ID] = entity_id

    await hass.services.async_call(
        DOMAIN, ClimateService.SET_HVAC_MODE, data, blocking=True
    )


def set_operation_mode(
    hass: HomeAssistant, hvac_mode: HVACMode, entity_id: str = ENTITY_MATCH_ALL
) -> None:
    """Set new target operation mode."""
    data = {ClimateServiceArgument.HVAC_MODE: hvac_mode}

    if entity_id is not None:
        data[TargetKey.ENTITY_ID] = entity_id

    hass.services.call(DOMAIN, ClimateService.SET_HVAC_MODE, data)


async def async_set_swing_horizontal_mode(
    hass: HomeAssistant, swing_horizontal_mode: str, entity_id: str = ENTITY_MATCH_ALL
) -> None:
    """Set new target swing horizontal mode."""
    data = {ClimateServiceArgument.SWING_HORIZONTAL_MODE: swing_horizontal_mode}

    if entity_id is not None:
        data[TargetKey.ENTITY_ID] = entity_id

    await hass.services.async_call(
        DOMAIN, ClimateService.SET_SWING_HORIZONTAL_MODE, data, blocking=True
    )


async def async_set_swing_mode(
    hass: HomeAssistant, swing_mode: str, entity_id: str = ENTITY_MATCH_ALL
) -> None:
    """Set new target swing mode."""
    data = {ClimateServiceArgument.SWING_MODE: swing_mode}

    if entity_id is not None:
        data[TargetKey.ENTITY_ID] = entity_id

    await hass.services.async_call(
        DOMAIN, ClimateService.SET_SWING_MODE, data, blocking=True
    )


def set_swing_mode(
    hass: HomeAssistant, swing_mode: str, entity_id: str = ENTITY_MATCH_ALL
) -> None:
    """Set new target swing mode."""
    data = {ClimateServiceArgument.SWING_MODE: swing_mode}

    if entity_id is not None:
        data[TargetKey.ENTITY_ID] = entity_id

    hass.services.call(DOMAIN, ClimateService.SET_SWING_MODE, data)


async def async_turn_on(hass: HomeAssistant, entity_id: str = ENTITY_MATCH_ALL) -> None:
    """Turn on device."""
    data = {}

    if entity_id is not None:
        data[TargetKey.ENTITY_ID] = entity_id

    await hass.services.async_call(DOMAIN, ClimateService.TURN_ON, data, blocking=True)


async def async_turn_off(
    hass: HomeAssistant, entity_id: str = ENTITY_MATCH_ALL
) -> None:
    """Turn off device."""
    data = {}

    if entity_id is not None:
        data[TargetKey.ENTITY_ID] = entity_id

    await hass.services.async_call(DOMAIN, ClimateService.TURN_OFF, data, blocking=True)
