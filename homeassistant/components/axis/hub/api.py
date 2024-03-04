"""Axis network device abstraction."""

from asyncio import timeout
from types import MappingProxyType
from typing import Any

import axis
from axis.configuration import Configuration

from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.httpx_client import get_async_client

from ..const import LOGGER
from ..errors import AuthenticationRequired, CannotConnect


async def get_axis_api(
    hass: HomeAssistant,
    config: MappingProxyType[str, Any],
) -> axis.AxisDevice:
    """Create a Axis device API."""
    session = get_async_client(hass, verify_ssl=False)

    device = axis.AxisDevice(
        Configuration(
            session,
            config[CONF_HOST],
            port=config[CONF_PORT],
            username=config[CONF_USERNAME],
            password=config[CONF_PASSWORD],
        )
    )

    try:
        async with timeout(30):
            await device.vapix.initialize()

        return device

    except axis.Unauthorized as err:
        LOGGER.warning(
            "Connected to device at %s but not registered", config[CONF_HOST]
        )
        raise AuthenticationRequired from err

    except (TimeoutError, axis.RequestError) as err:
        LOGGER.error("Error connecting to the Axis device at %s", config[CONF_HOST])
        raise CannotConnect from err

    except axis.AxisException as err:
        LOGGER.exception("Unknown Axis communication error occurred")
        raise AuthenticationRequired from err
