"""Services for the climate integration."""

import logging
from typing import TYPE_CHECKING, Any

import probatio

from homeassistant.const import (
    ATTR_TEMPERATURE,
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.util.unit_conversion import TemperatureConverter

from .const import (
    ATTR_FAN_MODE,
    ATTR_HUMIDITY,
    ATTR_HVAC_MODE,
    ATTR_PRESET_MODE,
    ATTR_SWING_HORIZONTAL_MODE,
    ATTR_SWING_MODE,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    DATA_COMPONENT,
    DOMAIN,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HUMIDITY,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_SWING_HORIZONTAL_MODE,
    SERVICE_SET_SWING_MODE,
    SERVICE_SET_TEMPERATURE,
    ClimateEntityFeature,
    HVACMode,
)

if TYPE_CHECKING:
    from . import ClimateEntity

_LOGGER = logging.getLogger(__name__)

CONVERTIBLE_ATTRIBUTE = [ATTR_TEMPERATURE, ATTR_TARGET_TEMP_LOW, ATTR_TARGET_TEMP_HIGH]


SET_TEMPERATURE_SCHEMA = probatio.All(
    probatio.AtLeastOne(ATTR_TEMPERATURE, ATTR_TARGET_TEMP_HIGH, ATTR_TARGET_TEMP_LOW),
    cv.make_entity_service_schema(
        {
            probatio.Exclusive(ATTR_TEMPERATURE, "temperature"): probatio.Coerce(float),
            probatio.Inclusive(ATTR_TARGET_TEMP_HIGH, "temperature"): probatio.Coerce(
                float
            ),
            probatio.Inclusive(ATTR_TARGET_TEMP_LOW, "temperature"): probatio.Coerce(
                float
            ),
            probatio.Optional(ATTR_HVAC_MODE): probatio.Coerce(HVACMode),
        }
    ),
)


async def _async_service_humidity_set(
    entity: ClimateEntity, service_call: ServiceCall
) -> None:
    """Handle set humidity service."""
    humidity = service_call.data[ATTR_HUMIDITY]
    min_humidity = entity.min_humidity
    max_humidity = entity.max_humidity
    _LOGGER.debug(
        "Check valid humidity %d in range %d - %d",
        humidity,
        min_humidity,
        max_humidity,
    )
    if humidity < min_humidity or humidity > max_humidity:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="humidity_out_of_range",
            translation_placeholders={
                "humidity": str(humidity),
                "min_humidity": str(min_humidity),
                "max_humidity": str(max_humidity),
            },
        )

    await entity.async_set_humidity(humidity)


async def _async_service_temperature_set(
    entity: ClimateEntity, service_call: ServiceCall
) -> None:
    """Handle set temperature service."""
    if (
        ATTR_TEMPERATURE in service_call.data
        and not entity.supported_features & ClimateEntityFeature.TARGET_TEMPERATURE
    ):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="missing_target_temperature_entity_feature",
        )
    if (
        ATTR_TARGET_TEMP_LOW in service_call.data
        and not entity.supported_features
        & ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
    ):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="missing_target_temperature_range_entity_feature",
        )

    hass = entity.hass
    kwargs: dict[str, Any] = {}
    min_temp = entity.min_temp
    max_temp = entity.max_temp
    temp_unit = entity.native_temperature_unit

    if (
        (target_low_temp := service_call.data.get(ATTR_TARGET_TEMP_LOW))
        and (target_high_temp := service_call.data.get(ATTR_TARGET_TEMP_HIGH))
        and target_low_temp > target_high_temp
    ):
        # Ensure target_low_temp is not higher than target_high_temp.
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="low_temp_higher_than_high_temp",
        )

    for value, temp in service_call.data.items():
        if value in CONVERTIBLE_ATTRIBUTE:
            kwargs[value] = check_temp = TemperatureConverter.convert(
                temp, hass.config.units.temperature_unit, temp_unit
            )

            _LOGGER.debug(
                "Check valid temperature %d %s (%d %s) in range %d %s - %d %s",
                check_temp,
                temp_unit,
                temp,
                hass.config.units.temperature_unit,
                min_temp,
                temp_unit,
                max_temp,
                temp_unit,
            )
            if check_temp < min_temp or check_temp > max_temp:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="temp_out_of_range",
                    translation_placeholders={
                        "check_temp": str(check_temp),
                        "min_temp": str(min_temp),
                        "max_temp": str(max_temp),
                    },
                )
        else:
            kwargs[value] = temp

    await entity.async_set_temperature(**kwargs)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the climate services."""
    component = hass.data[DATA_COMPONENT]

    component.async_register_entity_service(
        SERVICE_TURN_ON,
        None,
        "async_turn_on",
        [ClimateEntityFeature.TURN_ON],
    )
    component.async_register_entity_service(
        SERVICE_TURN_OFF,
        None,
        "async_turn_off",
        [ClimateEntityFeature.TURN_OFF],
    )
    component.async_register_entity_service(
        SERVICE_TOGGLE,
        None,
        "async_toggle",
        [ClimateEntityFeature.TURN_OFF, ClimateEntityFeature.TURN_ON],
    )
    component.async_register_entity_service(
        SERVICE_SET_HVAC_MODE,
        {probatio.Required(ATTR_HVAC_MODE): probatio.Coerce(HVACMode)},
        "async_handle_set_hvac_mode_service",
    )
    component.async_register_entity_service(
        SERVICE_SET_PRESET_MODE,
        {probatio.Required(ATTR_PRESET_MODE): cv.string},
        "async_handle_set_preset_mode_service",
        [ClimateEntityFeature.PRESET_MODE],
    )
    component.async_register_entity_service(
        SERVICE_SET_TEMPERATURE,
        SET_TEMPERATURE_SCHEMA,
        _async_service_temperature_set,
        [
            ClimateEntityFeature.TARGET_TEMPERATURE,
            ClimateEntityFeature.TARGET_TEMPERATURE_RANGE,
        ],
    )
    component.async_register_entity_service(
        SERVICE_SET_HUMIDITY,
        {probatio.Required(ATTR_HUMIDITY): probatio.Coerce(int)},
        _async_service_humidity_set,
        [ClimateEntityFeature.TARGET_HUMIDITY],
    )
    component.async_register_entity_service(
        SERVICE_SET_FAN_MODE,
        {probatio.Required(ATTR_FAN_MODE): cv.string},
        "async_handle_set_fan_mode_service",
        [ClimateEntityFeature.FAN_MODE],
    )
    component.async_register_entity_service(
        SERVICE_SET_SWING_MODE,
        {probatio.Required(ATTR_SWING_MODE): cv.string},
        "async_handle_set_swing_mode_service",
        [ClimateEntityFeature.SWING_MODE],
    )
    component.async_register_entity_service(
        SERVICE_SET_SWING_HORIZONTAL_MODE,
        {probatio.Required(ATTR_SWING_HORIZONTAL_MODE): cv.string},
        "async_handle_set_swing_horizontal_mode_service",
        [ClimateEntityFeature.SWING_HORIZONTAL_MODE],
    )
