"""Outgoing push for a triggered mobile_app subscription."""
# pylint: disable=home-assistant-use-runtime-data  # Uses legacy hass.data[DOMAIN] pattern

import asyncio
from http import HTTPStatus
import logging
from typing import Any

from aiohttp import ClientError, ClientSession

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from ..const import (
    ATTR_APP_DATA,
    ATTR_APP_ID,
    ATTR_APP_VERSION,
    ATTR_OS_VERSION,
    ATTR_PUSH_TOKEN,
    ATTR_PUSH_URL,
    ATTR_WEBHOOK_ID,
    DATA_CONFIG_ENTRIES,
    DATA_PUSH_SUBSCRIPTIONS,
    DOMAIN,
    PUSH_SUBSCRIPTION_ID,
    PUSH_SUBSCRIPTION_TARGET,
    PUSH_SUBSCRIPTION_TOKEN,
    PUSH_SUBSCRIPTION_TRIGGER,
)

_LOGGER = logging.getLogger(__name__)


@callback
def async_send_subscription_push(
    hass: HomeAssistant, webhook_id: str, sub_id: str
) -> None:
    """Forward a subscription update to the app's push URL (fire-and-forget)."""
    entry: ConfigEntry | None = hass.data[DOMAIN][DATA_CONFIG_ENTRIES].get(webhook_id)
    if entry is None:
        return
    sub = hass.data[DOMAIN][DATA_PUSH_SUBSCRIPTIONS].get(webhook_id, {}).get(sub_id)
    if sub is None:
        return
    # Cloud-push registrations only; websocket-channel devices get realtime
    # state another way and don't need this path.
    if ATTR_PUSH_URL not in entry.data.get(ATTR_APP_DATA, {}):
        return

    hass.async_create_background_task(
        _send_subscription_push(hass, entry, sub_id, sub),
        f"mobile_app_push_subscription_{webhook_id}_{sub_id}",
    )


async def _send_subscription_push(
    hass: HomeAssistant,
    entry: ConfigEntry,
    sub_id: str,
    sub: dict[str, Any],
) -> None:
    """Post update to the push proxy."""
    session: ClientSession = async_get_clientsession(hass)

    reg_info = {
        ATTR_APP_ID: entry.data[ATTR_APP_ID],
        ATTR_APP_VERSION: entry.data[ATTR_APP_VERSION],
        ATTR_WEBHOOK_ID: entry.data[ATTR_WEBHOOK_ID],
    }
    if ATTR_OS_VERSION in entry.data:
        reg_info[ATTR_OS_VERSION] = entry.data[ATTR_OS_VERSION]

    trigger: dict[str, Any] = {PUSH_SUBSCRIPTION_ID: sub_id}
    if (target := sub[PUSH_SUBSCRIPTION_TARGET]) is not None:
        trigger[PUSH_SUBSCRIPTION_TARGET] = target

    payload = {
        PUSH_SUBSCRIPTION_TRIGGER: trigger,
        ATTR_PUSH_TOKEN: sub[PUSH_SUBSCRIPTION_TOKEN],
        "registration_info": reg_info,
    }

    try:
        async with (
            asyncio.timeout(10),
            session.post(
                entry.data[ATTR_APP_DATA][ATTR_PUSH_URL], json=payload
            ) as response,
        ):
            if response.status not in (
                HTTPStatus.OK,
                HTTPStatus.CREATED,
                HTTPStatus.ACCEPTED,
            ):
                _LOGGER.debug(
                    "Subscription push to %s returned %s",
                    entry.title,
                    response.status,
                )
    except TimeoutError, ClientError:
        # Best-effort; the next state change retries.
        _LOGGER.debug(
            "Failed to send subscription push to %s", entry.title, exc_info=True
        )
