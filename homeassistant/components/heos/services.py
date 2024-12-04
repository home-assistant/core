"""Services for the HEOS integration."""

import functools
import logging

from pyheos import CommandFailedError, Heos, HeosError, const
import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .const import (
    ATTR_PASSWORD,
    ATTR_USERNAME,
    DOMAIN,
    SERVICE_SIGN_IN,
    SERVICE_SIGN_OUT,
)

_LOGGER = logging.getLogger(__name__)

HEOS_SIGN_IN_SCHEMA = vol.Schema(
    {vol.Required(ATTR_USERNAME): cv.string, vol.Required(ATTR_PASSWORD): cv.string}
)

HEOS_SIGN_OUT_SCHEMA = vol.Schema({})


def register(hass: HomeAssistant):
    """Register HEOS services."""
    hass.services.async_register(
        DOMAIN,
        SERVICE_SIGN_IN,
        functools.partial(_sign_in_handler, hass),
        schema=HEOS_SIGN_IN_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SIGN_OUT,
        functools.partial(_sign_out_handler, hass),
        schema=HEOS_SIGN_OUT_SCHEMA,
    )


def _get_controller(hass: HomeAssistant) -> Heos:
    """Get the controller from the service call."""

    if not (entries := hass.config_entries.async_entries(DOMAIN)):
        raise ServiceValidationError("HEOS entry not found")
    if (entry := entries[0]).state is not ConfigEntryState.LOADED:
        raise ServiceValidationError("HEOS entry is not loaded")
    return entry.runtime_data.controller_manager.controller


async def _sign_in_handler(hass: HomeAssistant, service: ServiceCall) -> None:
    """Sign in to the HEOS account."""

    controller = _get_controller(hass)
    if controller.connection_state != const.STATE_CONNECTED:
        _LOGGER.error("Unable to sign in because HEOS is not connected")
        return
    username = service.data[ATTR_USERNAME]
    password = service.data[ATTR_PASSWORD]
    try:
        await controller.sign_in(username, password)
    except CommandFailedError as err:
        _LOGGER.error("Sign in failed: %s", err)
    except HeosError as err:
        _LOGGER.error("Unable to sign in: %s", err)


async def _sign_out_handler(hass: HomeAssistant, service: ServiceCall) -> None:
    """Sign out of the HEOS account."""

    controller = _get_controller(hass)
    if controller.connection_state != const.STATE_CONNECTED:
        _LOGGER.error("Unable to sign out because HEOS is not connected")
        return
    try:
        await controller.sign_out()
    except HeosError as err:
        _LOGGER.error("Unable to sign out: %s", err)
