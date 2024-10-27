"""deCONZ API representation."""

from __future__ import annotations

import asyncio

from pydeconz import DeconzSession, errors

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client

from ..const import LOGGER
from ..errors import AuthenticationRequired, CannotConnect
from .config import DeconzConfig


async def get_deconz_api(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> DeconzSession:
    """Create a gateway object and verify configuration."""
    session = aiohttp_client.async_get_clientsession(hass)

    config = DeconzConfig.from_config_entry(config_entry)
    api = DeconzSession(session, config.host, config.port, config.api_key)
    try:
        async with asyncio.timeout(10):
            await api.refresh_state()

    except errors.Unauthorized as err:
        LOGGER.warning("Invalid key for deCONZ at %s", config.host)
        raise AuthenticationRequired from err

    except (TimeoutError, errors.RequestError, errors.ResponseError) as err:
        LOGGER.error("Error connecting to deCONZ gateway at %s", config.host)
        raise CannotConnect from err
    return api
