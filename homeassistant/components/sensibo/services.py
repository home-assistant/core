"""Sensibo services."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.components.climate import (
    ATTR_FAN_MODE,
    ATTR_HVAC_MODE,
    ATTR_SWING_MODE,
    DOMAIN as CLIMATE_DOMAIN,
    HVACMode,
)
from homeassistant.const import ATTR_MODE, ATTR_STATE
from homeassistant.core import HomeAssistant, SupportsResponse, callback
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN

SERVICE_ASSUME_STATE = "assume_state"
SERVICE_ENABLE_TIMER = "enable_timer"
ATTR_MINUTES = "minutes"
SERVICE_ENABLE_PURE_BOOST = "enable_pure_boost"
SERVICE_DISABLE_PURE_BOOST = "disable_pure_boost"
SERVICE_FULL_STATE = "full_state"
SERVICE_ENABLE_CLIMATE_REACT = "enable_climate_react"
SERVICE_GET_DEVICE_CAPABILITIES = "get_device_capabilities"
ATTR_HIGH_TEMPERATURE_THRESHOLD = "high_temperature_threshold"
ATTR_HIGH_TEMPERATURE_STATE = "high_temperature_state"
ATTR_LOW_TEMPERATURE_THRESHOLD = "low_temperature_threshold"
ATTR_LOW_TEMPERATURE_STATE = "low_temperature_state"
ATTR_SMART_TYPE = "smart_type"

ATTR_AC_INTEGRATION = "ac_integration"
ATTR_GEO_INTEGRATION = "geo_integration"
ATTR_INDOOR_INTEGRATION = "indoor_integration"
ATTR_OUTDOOR_INTEGRATION = "outdoor_integration"
ATTR_SENSITIVITY = "sensitivity"
ATTR_TARGET_TEMPERATURE = "target_temperature"
ATTR_HORIZONTAL_SWING_MODE = "horizontal_swing_mode"
ATTR_LIGHT = "light"
BOOST_INCLUSIVE = "boost_inclusive"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register Sonos services."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_ASSUME_STATE,
        entity_domain=CLIMATE_DOMAIN,
        schema={
            vol.Required(ATTR_STATE): vol.In(["on", "off"]),
        },
        func="async_assume_state",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_ENABLE_TIMER,
        entity_domain=CLIMATE_DOMAIN,
        schema={
            vol.Required(ATTR_MINUTES): cv.positive_int,
        },
        func="async_enable_timer",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_ENABLE_PURE_BOOST,
        entity_domain=CLIMATE_DOMAIN,
        schema={
            vol.Required(ATTR_AC_INTEGRATION): bool,
            vol.Required(ATTR_GEO_INTEGRATION): bool,
            vol.Required(ATTR_INDOOR_INTEGRATION): bool,
            vol.Required(ATTR_OUTDOOR_INTEGRATION): bool,
            vol.Required(ATTR_SENSITIVITY): vol.In(["normal", "sensitive"]),
        },
        func="async_enable_pure_boost",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_FULL_STATE,
        entity_domain=CLIMATE_DOMAIN,
        schema={
            vol.Required(ATTR_MODE): vol.In(
                ["cool", "heat", "fan", "auto", "dry", "off"]
            ),
            vol.Optional(ATTR_TARGET_TEMPERATURE): int,
            vol.Optional(ATTR_FAN_MODE): str,
            vol.Optional(ATTR_SWING_MODE): str,
            vol.Optional(ATTR_HORIZONTAL_SWING_MODE): str,
            vol.Optional(ATTR_LIGHT): vol.In(["on", "off", "dim"]),
        },
        func="async_full_ac_state",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_ENABLE_CLIMATE_REACT,
        entity_domain=CLIMATE_DOMAIN,
        schema={
            vol.Required(ATTR_HIGH_TEMPERATURE_THRESHOLD): vol.Coerce(float),
            vol.Required(ATTR_HIGH_TEMPERATURE_STATE): dict,
            vol.Required(ATTR_LOW_TEMPERATURE_THRESHOLD): vol.Coerce(float),
            vol.Required(ATTR_LOW_TEMPERATURE_STATE): dict,
            vol.Required(ATTR_SMART_TYPE): vol.In(
                ["temperature", "feelslike", "humidity"]
            ),
        },
        func="async_enable_climate_react",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_GET_DEVICE_CAPABILITIES,
        entity_domain=CLIMATE_DOMAIN,
        schema={vol.Required(ATTR_HVAC_MODE): vol.Coerce(HVACMode)},
        func="async_get_device_capabilities",
        supports_response=SupportsResponse.ONLY,
    )
