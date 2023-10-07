"""Webhook handling for the Monzo integration."""
import logging

from aiohttp.web import Request

from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import DOMAIN, EVENT_TRANSACTION_CREATED, MONZO_EVENT

_LOGGER = logging.getLogger(__name__)


async def async_handle_webhook(
    hass: HomeAssistant, webhook_id: str, request: Request
) -> None:
    """Handle webhook callback."""
    try:
        data = await request.json()
    except ValueError as err:
        _LOGGER.error("Error in data: %s", err)
        return None

    _LOGGER.debug("Got webhook data: %s", data)

    event_type = data.get("type")

    if event_type == EVENT_TRANSACTION_CREATED:
        async_send_event(hass, event_type, data.get("data"))
    else:
        _LOGGER.debug("Got unexpected event type from webhook: %s", event_type)


def async_send_event(hass: HomeAssistant, event_type: str, data: dict) -> None:
    """Send events."""
    _LOGGER.debug("%s: %s", event_type, data)
    async_dispatcher_send(
        hass,
        f"signal-{DOMAIN}-webhook-{event_type}",
        {"type": event_type, "data": data},
    )

    event_data = {"type": event_type, "data": data, "account_id": data["account_id"]}

    hass.bus.async_fire(
        event_type=MONZO_EVENT,
        event_data=event_data,
    )
