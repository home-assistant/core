"""Subscription information."""
from __future__ import annotations

import logging
from typing import Any

from aiohttp.client_exceptions import ClientError
import async_timeout
from hass_nabucasa import Cloud, cloud_api

from .const import REQUEST_TIMEOUT

_LOGGER = logging.getLogger(__name__)


async def async_subscription_info(cloud: Cloud) -> dict[str, Any] | None:
    """Fetch the subscription info."""
    try:
        async with async_timeout.timeout(REQUEST_TIMEOUT):
            return await cloud_api.async_subscription_info(cloud)
    except ClientError:
        _LOGGER.error("Failed to fetch subscription information")

    return None
