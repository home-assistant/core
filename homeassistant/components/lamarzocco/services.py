"""Global services for the La Marzocco integration."""

import asyncio
from collections.abc import Callable
import logging
from typing import TypedDict

import voluptuous as vol

from homeassistant.core import HomeAssistant
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

_LOGGER = logging.getLogger(__name__)

PLATFORM = "platform"


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
        _LOGGER.exception("Service call encountered error %s", str(ex))
        raise HomeAssistantError(ex) from ex


async def update_ha_state(coordinator):
    """Update the HA state."""
    await asyncio.sleep(UPDATE_DELAY)
    await coordinator.async_request_refresh()


async def async_setup_services(hass: HomeAssistant, config_entry):
    """Create and register services for the La Marzocco integration."""

    async def set_auto_on_off_enable(service):
        """Service call to enable auto on/off."""
        day_of_week = service.data.get("day_of_week", None)
        enable = service.data.get("enable", None)

        _LOGGER.debug("Setting auto on/off for %s to %s", day_of_week, enable)
        await call_service(
            lm.set_auto_on_off_enable, day_of_week=day_of_week, enable=enable
        )
        await update_ha_state(coordinator)
        return True

    async def set_auto_on_off_times(service):
        """Service call to configure auto on/off hours for a day."""
        day_of_week = service.data.get("day_of_week", None)
        hour_on = service.data.get("hour_on", None)
        minute_on = service.data.get("minute_on", None)
        hour_off = service.data.get("hour_off", None)
        minute_off = service.data.get("minute_off", None)

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

    async def set_dose(service):
        """Service call to set the dose for a key."""
        key = service.data.get("key", None)
        pulses = service.data.get("pulses", None)

        _LOGGER.debug("Setting dose for key: %s to pulses: %s", key, pulses)
        await call_service(lm.set_dose, key=key, pulses=pulses)
        await update_ha_state(coordinator)
        return True

    async def set_dose_hot_water(service):
        """Service call to set the hot water dose."""
        seconds = service.data.get("seconds", None)

        _LOGGER.debug("Setting hot water dose to seconds: %s", seconds)
        await call_service(lm.set_dose_hot_water, seconds=seconds)
        await update_ha_state(coordinator)
        return True

    async def set_prebrew_times(service):
        """Service call to set prebrew on time."""
        key = service.data.get("key", None)
        seconds_on = service.data.get("seconds_on", None)
        seconds_off = service.data.get("seconds_off", None)

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

    async def set_preinfusion_time(service):
        """Service call to set preinfusion time."""
        key = service.data.get("key", None)
        seconds = service.data.get("seconds", None)

        _LOGGER.debug("Setting prebrew on time for %s to %s", key, seconds)
        await call_service(
            lm.set_preinfusion_time,
            key=key,
            seconds=seconds,
        )
        await update_ha_state(coordinator)
        return True

    INTEGRATION_SERVICES: dict[str, IntegrationService] = {
        "set_dose": {
            "schema": {
                vol.Required("key"): vol.All(vol.Coerce(int), vol.Range(min=1, max=5)),
                vol.Required("pulses"): vol.All(
                    vol.Coerce(int), vol.Range(min=0, max=1000)
                ),
            },
            "supported": [MODEL_GS3_AV],
            "func": set_dose,
        },
        "set_dose_hot_water": {
            "schema": {
                vol.Required("seconds"): vol.All(
                    vol.Coerce(int), vol.Range(min=0, max=30)
                ),
            },
            "supported": [MODEL_GS3_AV, MODEL_GS3_MP],
            "func": set_dose_hot_water,
        },
        "set_auto_on_off_enable": {
            "schema": {
                vol.Required("day_of_week"): vol.In(DAYS),
                vol.Required("enable"): vol.Boolean(),
            },
            "supported": [MODEL_GS3_AV, MODEL_GS3_MP, MODEL_LM, MODEL_LMU],
            "func": set_auto_on_off_enable,
        },
        "set_auto_on_off_times": {
            "schema": {
                vol.Required("day_of_week"): vol.In(DAYS),
                vol.Required("hour_on"): vol.All(
                    vol.Coerce(int), vol.Range(min=0, max=23)
                ),
                vol.Optional("minute_on", default=0): vol.All(
                    vol.Coerce(int), vol.Range(min=0, max=59)
                ),
                vol.Required("hour_off"): vol.All(
                    vol.Coerce(int), vol.Range(min=0, max=23)
                ),
                vol.Optional("minute_off", default=0): vol.All(
                    vol.Coerce(int), vol.Range(min=0, max=59)
                ),
            },
            "supported": [MODEL_GS3_AV, MODEL_GS3_MP, MODEL_LM, MODEL_LMU],
            "func": set_auto_on_off_times,
        },
        "set_prebrew_times": {
            "schema": {
                vol.Required("seconds_on"): vol.All(
                    vol.Coerce(float), vol.Range(min=0, max=5.9)
                ),
                vol.Required("seconds_off"): vol.All(
                    vol.Coerce(float), vol.Range(min=0, max=5.9)
                ),
            },
            "supported": [MODEL_GS3_AV, MODEL_LM, MODEL_LMU],
            "func": set_prebrew_times,
        },
        "set_preinfusion_time": {
            "schema": {
                vol.Required("seconds"): vol.All(
                    vol.Coerce(float), vol.Range(min=0, max=24.9)
                ),
            },
            "supported": [MODEL_GS3_AV, MODEL_LM, MODEL_LMU],
            "func": set_preinfusion_time,
        },
    }

    existing_services = hass.services.async_services().get(DOMAIN)
    if existing_services and any(
        service in INTEGRATION_SERVICES for service in existing_services
    ):
        # Integration-level services have already been added. Return.
        return

    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    lm = coordinator.data

    # Set the max prebrew button based on model
    if lm.model_name in [MODEL_GS3_AV, MODEL_LM, MODEL_LMU]:
        max_button_number = 4 if lm.model_name == MODEL_GS3_AV else 1
        INTEGRATION_SERVICES["set_prebrew_times"]["schema"].update(
            {
                vol.Required("key"): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=max_button_number)
                )
            },
        )
        INTEGRATION_SERVICES["set_preinfusion_time"]["schema"].update(
            {
                vol.Required("key"): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=max_button_number)
                )
            },
        )

    # set the services up
    for name, service in INTEGRATION_SERVICES.items():
        if lm.model_name in service["supported"]:
            hass.services.async_register(
                domain=DOMAIN,
                service=name,
                schema=vol.Schema(service["schema"]),
                service_func=service["func"],
            )
