"""Provide an object to communicate with UniFi Network application."""

import asyncio
from collections.abc import Mapping
from functools import partial
import ssl
from typing import Any, Literal

from aiohttp import CookieJar
import aiounifi
from aiounifi.models.configuration import Configuration

from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client
from homeassistant.util import ssl as ssl_util

from ..const import CONF_SITE_ID, LOGGER
from ..errors import AuthenticationRequired, CannotConnect, MfaRequired


async def get_unifi_api(
    hass: HomeAssistant,
    config: Mapping[str, Any],
) -> aiounifi.Controller:
    """Create a aiounifi object and verify authentication."""
    ssl_context: ssl.SSLContext | Literal[False] = False

    if verify_ssl := config.get(CONF_VERIFY_SSL):
        session = aiohttp_client.async_get_clientsession(hass)
        if isinstance(verify_ssl, str):
            ssl_context = await hass.async_add_executor_job(
                partial(ssl.create_default_context, cafile=verify_ssl)
            )
        else:
            ssl_context = ssl_util.get_default_context()
    else:
        session = aiohttp_client.async_create_clientsession(
            hass, verify_ssl=False, cookie_jar=CookieJar(unsafe=True)
        )

    api = aiounifi.Controller(
        Configuration(
            session,
            host=config[CONF_HOST],
            username=config[CONF_USERNAME],
            password=config[CONF_PASSWORD],
            port=config[CONF_PORT],
            site=config[CONF_SITE_ID],
            ssl_context=ssl_context,
        )
    )

    try:
        async with asyncio.timeout(10):
            await api.login()

    except aiounifi.TwoFaTokenRequired as err:
        LOGGER.warning(
            "UniFi Network at %s requires multi-factor authentication, which is"
            " not supported. Use a local account without multi-factor"
            " authentication",
            config[CONF_HOST],
        )
        raise MfaRequired from err

    except aiounifi.Unauthorized as err:
        LOGGER.warning(
            "Connected to UniFi Network at %s but not registered: %s",
            config[CONF_HOST],
            err,
        )
        raise AuthenticationRequired from err

    except (
        TimeoutError,
        aiounifi.AuthenticationRateLimitError,
        aiounifi.BadGateway,
        aiounifi.Forbidden,
        aiounifi.ServiceUnavailable,
        aiounifi.RequestError,
        aiounifi.ResponseError,
    ) as err:
        LOGGER.error(
            "Error connecting to the UniFi Network at %s: %s", config[CONF_HOST], err
        )
        raise CannotConnect from err

    except aiounifi.LoginRequired as err:
        LOGGER.warning(
            "Connected to UniFi Network at %s but login required: %s",
            config[CONF_HOST],
            err,
        )
        raise AuthenticationRequired from err

    except aiounifi.AiounifiException as err:
        LOGGER.exception("Unknown UniFi Network communication error occurred: %s", err)
        raise AuthenticationRequired from err

    return api
