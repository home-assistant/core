"""Services for the HEOS integration."""
import asyncio
import functools
import logging

from pyheos import CommandError, Heos, const
import voluptuous as vol

from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import HomeAssistantType

from .const import (
    ATTR_PASSWORD, ATTR_USERNAME, DOMAIN, SERVICE_SIGN_IN, SERVICE_SIGN_OUT)

_LOGGER = logging.getLogger(__name__)

HEOS_SIGN_IN_SCHEMA = vol.Schema({
    vol.Required(ATTR_USERNAME): cv.string,
    vol.Required(ATTR_PASSWORD): cv.string
})

HEOS_SIGN_OUT_SCHEMA = vol.Schema({})


def register(hass: HomeAssistantType, controller: Heos):
    """Register HEOS services."""
    hass.services.async_register(
        DOMAIN, SERVICE_SIGN_IN,
        functools.partial(_sign_in_handler, controller),
        schema=HEOS_SIGN_IN_SCHEMA)
    hass.services.async_register(
        DOMAIN, SERVICE_SIGN_OUT,
        functools.partial(_sign_out_handler, controller),
        schema=HEOS_SIGN_OUT_SCHEMA)


def remove(hass: HomeAssistantType):
    """Unregister HEOS services."""
    hass.services.async_remove(DOMAIN, SERVICE_SIGN_IN)
    hass.services.async_remove(DOMAIN, SERVICE_SIGN_OUT)


async def _sign_in_handler(controller, service):
    """Sign in to the HEOS account."""
    if controller.connection_state != const.STATE_CONNECTED:
        _LOGGER.error("Unable to sign in because HEOS is not connected")
        return
    username = service.data[ATTR_USERNAME]
    password = service.data[ATTR_PASSWORD]
    try:
        await controller.sign_in(username, password)
    except CommandError as err:
        _LOGGER.error("Sign in failed: %s", err)
    except (asyncio.TimeoutError, ConnectionError) as err:
        _LOGGER.error("Unable to sign in: %s", err)


async def _sign_out_handler(controller, service):
    """Sign out of the HEOS account."""
    if controller.connection_state != const.STATE_CONNECTED:
        _LOGGER.error("Unable to sign out because HEOS is not connected")
        return
    try:
        await controller.sign_out()
    except (asyncio.TimeoutError, ConnectionError, CommandError) as err:
        _LOGGER.error("Unable to sign out: %s", err)
