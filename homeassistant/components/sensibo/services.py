"""Sensibo services."""

from enum import StrEnum

import probatio

from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN, HVACMode
from homeassistant.core import HomeAssistant, SupportsResponse, callback
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN


class SensiboService(StrEnum):
    """Store keys for Sensibo services."""

    ASSUME_STATE = "assume_state"
    ENABLE_TIMER = "enable_timer"
    ENABLE_PURE_BOOST = "enable_pure_boost"
    FULL_STATE = "full_state"
    ENABLE_CLIMATE_REACT = "enable_climate_react"
    GET_DEVICE_CAPABILITIES = "get_device_capabilities"


class SensiboServiceArgument(StrEnum):
    """Store keys for Sensibo service arguments."""

    STATE = "state"
    MINUTES = "minutes"
    AC_INTEGRATION = "ac_integration"
    GEO_INTEGRATION = "geo_integration"
    INDOOR_INTEGRATION = "indoor_integration"
    OUTDOOR_INTEGRATION = "outdoor_integration"
    SENSITIVITY = "sensitivity"
    MODE = "mode"
    TARGET_TEMPERATURE = "target_temperature"
    FAN_MODE = "fan_mode"
    SWING_MODE = "swing_mode"
    HORIZONTAL_SWING_MODE = "horizontal_swing_mode"
    LIGHT = "light"
    HIGH_TEMPERATURE_THRESHOLD = "high_temperature_threshold"
    HIGH_TEMPERATURE_STATE = "high_temperature_state"
    LOW_TEMPERATURE_THRESHOLD = "low_temperature_threshold"
    LOW_TEMPERATURE_STATE = "low_temperature_state"
    SMART_TYPE = "smart_type"
    HVAC_MODE = "hvac_mode"


BOOST_INCLUSIVE = "boost_inclusive"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register Sensibo services."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SensiboService.ASSUME_STATE,
        entity_domain=CLIMATE_DOMAIN,
        schema={
            probatio.Required(SensiboServiceArgument.STATE): probatio.In(["on", "off"]),
        },
        func="async_assume_state",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SensiboService.ENABLE_TIMER,
        entity_domain=CLIMATE_DOMAIN,
        schema={
            probatio.Required(SensiboServiceArgument.MINUTES): cv.positive_int,
        },
        func="async_enable_timer",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SensiboService.ENABLE_PURE_BOOST,
        entity_domain=CLIMATE_DOMAIN,
        schema={
            probatio.Required(SensiboServiceArgument.AC_INTEGRATION): bool,
            probatio.Required(SensiboServiceArgument.GEO_INTEGRATION): bool,
            probatio.Required(SensiboServiceArgument.INDOOR_INTEGRATION): bool,
            probatio.Required(SensiboServiceArgument.OUTDOOR_INTEGRATION): bool,
            probatio.Required(SensiboServiceArgument.SENSITIVITY): probatio.In(
                ["normal", "sensitive"]
            ),
        },
        func="async_enable_pure_boost",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SensiboService.FULL_STATE,
        entity_domain=CLIMATE_DOMAIN,
        schema={
            probatio.Required(SensiboServiceArgument.MODE): probatio.In(
                ["cool", "heat", "fan", "auto", "dry", "off"]
            ),
            probatio.Optional(SensiboServiceArgument.TARGET_TEMPERATURE): int,
            probatio.Optional(SensiboServiceArgument.FAN_MODE): str,
            probatio.Optional(SensiboServiceArgument.SWING_MODE): str,
            probatio.Optional(SensiboServiceArgument.HORIZONTAL_SWING_MODE): str,
            probatio.Optional(SensiboServiceArgument.LIGHT): probatio.In(
                ["on", "off", "dim"]
            ),
        },
        func="async_full_ac_state",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SensiboService.ENABLE_CLIMATE_REACT,
        entity_domain=CLIMATE_DOMAIN,
        schema={
            probatio.Required(
                SensiboServiceArgument.HIGH_TEMPERATURE_THRESHOLD
            ): probatio.Coerce(float),
            probatio.Required(SensiboServiceArgument.HIGH_TEMPERATURE_STATE): dict,
            probatio.Required(
                SensiboServiceArgument.LOW_TEMPERATURE_THRESHOLD
            ): probatio.Coerce(float),
            probatio.Required(SensiboServiceArgument.LOW_TEMPERATURE_STATE): dict,
            probatio.Required(SensiboServiceArgument.SMART_TYPE): probatio.In(
                ["temperature", "feelslike", "humidity"]
            ),
        },
        func="async_enable_climate_react",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SensiboService.GET_DEVICE_CAPABILITIES,
        entity_domain=CLIMATE_DOMAIN,
        schema={
            probatio.Required(SensiboServiceArgument.HVAC_MODE): probatio.Coerce(
                HVACMode
            )
        },
        func="async_get_device_capabilities",
        supports_response=SupportsResponse.ONLY,
    )
