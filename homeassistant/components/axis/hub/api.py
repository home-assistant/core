"""Axis network device abstraction."""

from asyncio import timeout
from collections.abc import Mapping
from typing import Any

import axis
from axis.models.configuration import Configuration

from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_PROTOCOL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from ..const import CONF_COMPANION, LOGGER
from ..errors import AuthenticationRequired, CannotConnect


async def get_axis_api(
    hass: HomeAssistant,
    config: Mapping[str, Any],
) -> axis.AxisDevice:
    """Create a Axis device API."""
    session = async_get_clientsession(hass, verify_ssl=False)

    api = axis.AxisDevice(
        Configuration(
            session,
            config[CONF_HOST],
            port=config[CONF_PORT],
            username=config[CONF_USERNAME],
            password=config[CONF_PASSWORD],
            web_proto=config.get(CONF_PROTOCOL, "http"),
            websocket_enabled=True,
        )
    )

    try:
        async with timeout(30):
            await api.vapix.initialize()

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

    # Companion devices reject initialization requests with Axis-Orig-Sw
    if CONF_COMPANION in config:
        api.config.is_companion = config[CONF_COMPANION]

    return api


def is_companion_device(api: axis.AxisDevice) -> bool:
    """Return if device belongs to the AXIS Companion product line."""
    vapix = api.vapix
    handler = (
        vapix.basic_device_info
        if vapix.basic_device_info.initialized
        else vapix.params.brand_handler
    )
    return (item := handler.get("0")) is not None and (
        "Companion" in item.product_full_name
    )
