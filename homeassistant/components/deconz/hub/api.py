"""deCONZ API representation."""

from __future__ import annotations

import asyncio
from types import MappingProxyType
from typing import Any

from pydeconz import DeconzSession, errors

from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client

from ..const import LOGGER
from ..errors import AuthenticationRequired, CannotConnect


async def get_deconz_api(
    hass: HomeAssistant, config: MappingProxyType[str, Any]
) -> DeconzSession:
    """Create a gateway object and verify configuration."""
    session = aiohttp_client.async_get_clientsession(hass)

    api = DeconzSession(
        session, config[CONF_HOST], config[CONF_PORT], config[CONF_API_KEY]
    )
    try:
        async with asyncio.timeout(10):
            await api.refresh_state()
        return api

    except errors.Unauthorized as err:
        LOGGER.warning("Invalid key for deCONZ at %s", config[CONF_HOST])
        raise AuthenticationRequired from err

    except (TimeoutError, errors.RequestError, errors.ResponseError) as err:
        LOGGER.error("Error connecting to deCONZ gateway at %s", config[CONF_HOST])
        raise CannotConnect from err
