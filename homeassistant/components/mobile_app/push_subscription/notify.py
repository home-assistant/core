"""Outgoing silent push for a triggered subscription.

Sends a minimal data-only payload to the same push proxy URL the device
registered (entry.data[app_data][push_url]) so the push relay can format it as
a background/silent push. No message/title is included, so it never surfaces as
a user-visible notification.
"""
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
    """Schedule a silent push for one subscription (fire-and-forget)."""
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
    """Post the silent payload to the push proxy."""
    session: ClientSession = async_get_clientsession(hass)

    reg_info = {
        ATTR_APP_ID: entry.data[ATTR_APP_ID],
        ATTR_APP_VERSION: entry.data[ATTR_APP_VERSION],
        ATTR_WEBHOOK_ID: entry.data[ATTR_WEBHOOK_ID],
    }
    if ATTR_OS_VERSION in entry.data:
        reg_info[ATTR_OS_VERSION] = entry.data[ATTR_OS_VERSION]

    # Deliberately minimal + generic. The relay sees PUSH_SUBSCRIPTION_TRIGGER
    # and knows to build a silent background push (no alert or sound). `target`
    # is the app's opaque hint for which surface to reload.
    payload = {
        PUSH_SUBSCRIPTION_TRIGGER: {
            PUSH_SUBSCRIPTION_ID: sub_id,
            PUSH_SUBSCRIPTION_TARGET: sub[PUSH_SUBSCRIPTION_TARGET],
        },
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
        #  Silent pushes are best-effort; the next state change retries.
        _LOGGER.debug(
            "Failed to send subscription push to %s", entry.title, exc_info=True
        )
