"""Init the tedee component."""
import asyncio
from collections.abc import Awaitable, Callable
from http import HTTPStatus
import logging
from typing import Any

from aiohttp.hdrs import METH_POST
from aiohttp.web import Request, Response
from pytedee_async.exception import TedeeWebhookException

from homeassistant.components.http import HomeAssistantView
from homeassistant.components.webhook import (
    async_generate_id as webhook_generate_id,
    async_generate_url as webhook_generate_url,
    async_register as webhook_register,
    async_unregister as webhook_unregister,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_WEBHOOK_ID, EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN, NAME
from .coordinator import TedeeApiCoordinator

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.LOCK,
    Platform.SENSOR,
]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Integration setup."""

    if CONF_WEBHOOK_ID not in entry.data:
        new_data = entry.data.copy()
        new_data[CONF_WEBHOOK_ID] = webhook_generate_id()
        hass.config_entries.async_update_entry(entry, data=new_data)

    coordinator = TedeeApiCoordinator(hass)

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    webhook_registered = False
    register_lock = asyncio.Lock()

    async def unregister_webhook(_: Any) -> None:
        nonlocal webhook_registered
        async with register_lock:
            if not webhook_registered:
                return
            await coordinator.tedee_client.delete_webhooks()
            webhook_unregister(hass, entry.data[CONF_WEBHOOK_ID])
            _LOGGER.debug("Unregistered Tedee webhook")

    async def register_webhook() -> None:
        nonlocal webhook_registered
        async with register_lock:
            if webhook_registered:
                return
            webhook_url = webhook_generate_url(hass, entry.data[CONF_WEBHOOK_ID])
            webhook_name = "Tedee"
            if entry.title != NAME:
                webhook_name = f"{NAME} {entry.title}"

            webhook_register(
                hass,
                DOMAIN,
                webhook_name,
                entry.data[CONF_WEBHOOK_ID],
                get_webhook_handler(coordinator),
                allowed_methods=[METH_POST],
            )
            _LOGGER.debug("Registered Tedee webhook at hass: %s", webhook_url)

            await coordinator.tedee_client.register_webhook(webhook_url)
            entry.async_on_unload(
                hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, unregister_webhook)
            )
            webhook_registered = True

    entry.async_create_background_task(
        hass, register_webhook(), "tedee_register_webhook"
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


def get_webhook_handler(
    coordinator: TedeeApiCoordinator,
) -> Callable[[HomeAssistant, str, Request], Awaitable[Response | None]]:
    """Return webhook handler."""

    async def async_webhook_handler(
        hass: HomeAssistant, webhook_id: str, request: Request
    ) -> Response | None:
        # Handle http post calls to the path.
        if not request.body_exists:
            return HomeAssistantView.json(
                result="No Body", status_code=HTTPStatus.BAD_REQUEST
            )

        body = await request.json()
        try:
            coordinator.webhook_received(body)
        except TedeeWebhookException as ex:
            return HomeAssistantView.json(
                result=str(ex), status_code=HTTPStatus.BAD_REQUEST
            )

        return HomeAssistantView.json(result="OK", status_code=HTTPStatus.OK)

    return async_webhook_handler
