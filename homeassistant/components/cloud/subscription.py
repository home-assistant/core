"""Subscription information."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from aiohttp.client_exceptions import ClientError
from hass_nabucasa import Cloud, cloud_api
from hass_nabucasa.payments_api import PaymentsApiError, SubscriptionInfo

from .client import CloudClient
from .const import REQUEST_TIMEOUT

_LOGGER = logging.getLogger(__name__)


async def async_subscription_info(cloud: Cloud[CloudClient]) -> SubscriptionInfo | None:
    """Fetch the subscription info."""
    try:
        async with asyncio.timeout(REQUEST_TIMEOUT):
            return await cloud.payments.subscription_info()
    except PaymentsApiError as exception:
        _LOGGER.error("Failed to fetch subscription information - %s", exception)

    return None


async def async_migrate_paypal_agreement(
    cloud: Cloud[CloudClient],
) -> dict[str, Any] | None:
    """Migrate a paypal agreement from legacy."""
    try:
        async with asyncio.timeout(REQUEST_TIMEOUT):
            return await cloud_api.async_migrate_paypal_agreement(cloud)
    except TimeoutError:
        _LOGGER.error(
            "A timeout of %s was reached while trying to start agreement migration",
            REQUEST_TIMEOUT,
        )
    except ClientError as exception:
        _LOGGER.error("Failed to start agreement migration - %s", exception)

    return None
