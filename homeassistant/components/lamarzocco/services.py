"""Global services for the La Marzocco integration."""
# mypy: disable-error-code="literal-required, misc"
# Mypy  doesn't like variables as keys in a typeddict, so we have to disable this error

import asyncio
from collections.abc import Callable
import logging
from typing import TypedDict

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError

from .const import (
    DAYS,
    DOMAIN,
    MODEL_GS3_AV,
    MODEL_GS3_MP,
    MODEL_LM,
    MODEL_LMU,
    UPDATE_DELAY,
)
from .coordinator import LmApiCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORM = "platform"
SCHEMA = "schema"
SUPPORTED = "supported"
FUNC = "func"

SERVICE_DOSE = "set_dose"
SERVICE_DOSE_HOT_WATER = "set_dose_hot_water"
SERVICE_AUTO_ON_OFF_ENABLE = "set_auto_on_off_enable"
SERVICE_AUTO_ON_OFF_TIMES = "set_auto_on_off_times"
SERVICE_PREBREW_TIMES = "set_prebrew_times"
SERVICE_PREINFUSION_TIME = "set_preinfusion_time"

CONF_DAY_OF_WEEK = "day_of_week"
CONF_ENABLE = "enable"
CONF_HOUR_ON = "hour_on"
CONF_HOUR_OFF = "hour_off"
CONF_MINUTE_ON = "minute_on"
CONF_MINUTE_OFF = "minute_off"
CONF_SECONDS_ON = "seconds_on"
CONF_SECONDS_OFF = "seconds_off"
CONF_SECONDS = "seconds"
CONF_KEY = "key"
CONF_PULSES = "pulses"


class IntegrationService(TypedDict):
    """Integration service type."""

    schema: vol.Schema
    supported: list[str]
    func: Callable


async def call_service(func, *args, **kwargs):
    """Call a service and handle exceptions."""
    try:
        await func(*args, **kwargs)
    except Exception as ex:
        raise HomeAssistantError("Service call encountered error: %s" % str(ex)) from ex


async def update_ha_state(coordinator: LmApiCoordinator):
    """Update the HA state."""
    await asyncio.sleep(UPDATE_DELAY)
    await coordinator.async_request_refresh()


async def async_setup_services(hass: HomeAssistant, entry: ConfigEntry):
    """Create and register services for the La Marzocco integration."""

    async def set_auto_on_off_enable(service: ServiceCall):
        """Service call to enable auto on/off."""
        day_of_week = service.data[CONF_DAY_OF_WEEK]
        enable = service.data[CONF_ENABLE]

        _LOGGER.debug("Setting auto on/off for %s to %s", day_of_week, enable)
        await call_service(
            lm.set_auto_on_off_enable, day_of_week=day_of_week, enable=enable
        )
        await update_ha_state(coordinator)
        return True

    async def set_auto_on_off_times(service: ServiceCall):
        """Service call to configure auto on/off hours for a day."""
        day_of_week = service.data[CONF_DAY_OF_WEEK]
        hour_on = service.data[CONF_HOUR_ON]
        minute_on = service.data[CONF_MINUTE_ON]
        hour_off = service.data[CONF_HOUR_OFF]
        minute_off = service.data[CONF_MINUTE_OFF]

        _LOGGER.debug(
            "Setting auto on/off hours for %s from %s:%s to %s:%s",
            day_of_week,
            hour_on,
            minute_on,
            hour_off,
            minute_off,
        )
        await call_service(
            lm.set_auto_on_off,
            day_of_week=day_of_week,
            hour_on=hour_on,
            minute_on=minute_on,
            hour_off=hour_off,
            minute_off=minute_off,
        )
        await update_ha_state(coordinator)
        return True

    async def set_dose(service: ServiceCall):
        """Service call to set the dose for a key."""
        key = service.data[CONF_KEY]
        pulses = service.data[CONF_PULSES]

        _LOGGER.debug("Setting dose for key: %s to pulses: %s", key, pulses)
        await call_service(lm.set_dose, key=key, value=pulses)
        await update_ha_state(coordinator)
        return True

    async def set_dose_hot_water(service: ServiceCall):
        """Service call to set the hot water dose."""
        seconds = service.data[CONF_SECONDS]

        _LOGGER.debug("Setting hot water dose to seconds: %s", seconds)
        await call_service(lm.set_dose_hot_water, value=seconds)
        await update_ha_state(coordinator)
        return True

    async def set_prebrew_times(service: ServiceCall):
        """Service call to set prebrew on time."""
        key = service.data[CONF_KEY]
        seconds_on = service.data[CONF_SECONDS_ON]
        seconds_off = service.data[CONF_SECONDS_OFF]

        _LOGGER.debug(
            "Setting prebrew on time for %s to %s and %s", key, seconds_on, seconds_off
        )
        await call_service(
            lm.set_prebrew_times,
            key=key,
            seconds_on=seconds_on,
            seconds_off=seconds_off,
        )
        await update_ha_state(coordinator)
        return True

    async def set_preinfusion_time(service: ServiceCall):
        """Service call to set preinfusion time."""
        key = service.data[CONF_KEY]
        seconds = service.data[CONF_SECONDS]

        _LOGGER.debug("Setting prebrew on time for %s to %s", key, seconds)
        await call_service(
            lm.set_preinfusion_time,
            key=key,
            seconds=seconds,
        )
        await update_ha_state(coordinator)
        return True

    INTEGRATION_SERVICES: dict[str, IntegrationService] = {
        SERVICE_DOSE: {
            SCHEMA: {
                vol.Required(CONF_KEY): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=5)
                ),
                vol.Required(CONF_PULSES): vol.All(
                    vol.Coerce(int), vol.Range(min=0, max=1000)
                ),
            },
            SUPPORTED: [MODEL_GS3_AV],
            FUNC: set_dose,
        },
        SERVICE_DOSE_HOT_WATER: {
            SCHEMA: {
                vol.Required("seconds"): vol.All(
                    vol.Coerce(int), vol.Range(min=0, max=30)
                ),
            },
            SUPPORTED: [MODEL_GS3_AV, MODEL_GS3_MP],
            FUNC: set_dose_hot_water,
        },
        SERVICE_AUTO_ON_OFF_ENABLE: {
            SCHEMA: {
                vol.Required(CONF_DAY_OF_WEEK): vol.In(DAYS),
                vol.Required(CONF_ENABLE): vol.Boolean(),
            },
            SUPPORTED: [MODEL_GS3_AV, MODEL_GS3_MP, MODEL_LM, MODEL_LMU],
            FUNC: set_auto_on_off_enable,
        },
        SERVICE_AUTO_ON_OFF_TIMES: {
            SCHEMA: {
                vol.Required(CONF_DAY_OF_WEEK): vol.In(DAYS),
                vol.Required(CONF_HOUR_ON): vol.All(
                    vol.Coerce(int), vol.Range(min=0, max=23)
                ),
                vol.Optional(CONF_MINUTE_ON, default=0): vol.All(
                    vol.Coerce(int), vol.Range(min=0, max=59)
                ),
                vol.Required(CONF_HOUR_OFF): vol.All(
                    vol.Coerce(int), vol.Range(min=0, max=23)
                ),
                vol.Optional(CONF_MINUTE_OFF, default=0): vol.All(
                    vol.Coerce(int), vol.Range(min=0, max=59)
                ),
            },
            SUPPORTED: [MODEL_GS3_AV, MODEL_GS3_MP, MODEL_LM, MODEL_LMU],
            FUNC: set_auto_on_off_times,
        },
        SERVICE_PREBREW_TIMES: {
            SCHEMA: {
                vol.Required(CONF_SECONDS_ON): vol.All(
                    vol.Coerce(float), vol.Range(min=0, max=5.9)
                ),
                vol.Required(CONF_SECONDS_OFF): vol.All(
                    vol.Coerce(float), vol.Range(min=0, max=5.9)
                ),
            },
            SUPPORTED: [MODEL_GS3_AV, MODEL_LM, MODEL_LMU],
            FUNC: set_prebrew_times,
        },
        SERVICE_PREINFUSION_TIME: {
            SCHEMA: {
                vol.Required(CONF_SECONDS): vol.All(
                    vol.Coerce(float), vol.Range(min=0, max=24.9)
                ),
            },
            SUPPORTED: [MODEL_GS3_AV, MODEL_LM, MODEL_LMU],
            FUNC: set_preinfusion_time,
        },
    }

    existing_services = hass.services.async_services().get(DOMAIN)
    if existing_services and any(
        service in INTEGRATION_SERVICES for service in existing_services
    ):
        # Integration-level services have already been added. Return.
        return

    coordinator = hass.data[DOMAIN][entry.entry_id]
    lm = coordinator.data

    # Set the max prebrew button based on model
    if lm.model_name in [MODEL_GS3_AV, MODEL_LM, MODEL_LMU]:
        max_button_number = 4 if lm.model_name == MODEL_GS3_AV else 1
        INTEGRATION_SERVICES[SERVICE_PREBREW_TIMES][SCHEMA].update(
            {
                vol.Required(CONF_KEY): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=max_button_number)
                )
            },
        )
        INTEGRATION_SERVICES[SERVICE_PREINFUSION_TIME][SCHEMA].update(
            {
                vol.Required(CONF_KEY): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=max_button_number)
                )
            },
        )

    # set the services up
    for name, service in INTEGRATION_SERVICES.items():
        if lm.model_name in service[SUPPORTED]:
            hass.services.async_register(
                domain=DOMAIN,
                service=name,
                schema=vol.Schema(service[SCHEMA]),
                service_func=service[FUNC],
            )
