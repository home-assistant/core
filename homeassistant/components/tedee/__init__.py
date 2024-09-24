"""Init the tedee component."""

from collections.abc import Awaitable, Callable
from http import HTTPStatus
import logging
from typing import Any

from aiohttp.hdrs import METH_POST
from aiohttp.web import Request, Response
from pytedee_async.exception import TedeeDataUpdateException, TedeeWebhookException

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
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.network import get_url

from .const import DOMAIN, NAME
from .coordinator import TedeeApiCoordinator

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.LOCK,
    Platform.SENSOR,
]

_LOGGER = logging.getLogger(__name__)

type TedeeConfigEntry = ConfigEntry[TedeeApiCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: TedeeConfigEntry) -> bool:
    """Integration setup."""

    coordinator = TedeeApiCoordinator(hass)

    await coordinator.async_config_entry_first_refresh()

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, coordinator.bridge.serial)},
        manufacturer="Tedee",
        name=coordinator.bridge.name,
        model="Bridge",
        serial_number=coordinator.bridge.serial,
    )

    entry.runtime_data = coordinator

    async def unregister_webhook(_: Any) -> None:
        await coordinator.async_unregister_webhook()
        webhook_unregister(hass, entry.data[CONF_WEBHOOK_ID])

    async def register_webhook() -> None:
        instance_url = get_url(hass, allow_ip=True, allow_external=False)
        # first make sure we don't have leftover callbacks to the same instance
        try:
            await coordinator.tedee_client.cleanup_webhooks_by_host(instance_url)
        except (TedeeDataUpdateException, TedeeWebhookException) as ex:
            _LOGGER.warning("Failed to cleanup Tedee webhooks by host: %s", ex)

        webhook_url = webhook_generate_url(
            hass, entry.data[CONF_WEBHOOK_ID], allow_external=False, allow_ip=True
        )
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

        try:
            await coordinator.async_register_webhook(webhook_url)
        except TedeeWebhookException:
            _LOGGER.exception("Failed to register Tedee webhook from bridge")
        else:
            entry.async_on_unload(
                hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, unregister_webhook)
            )

    entry.async_create_background_task(
        hass, register_webhook(), "tedee_register_webhook"
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


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


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    if config_entry.version > 1:
        # This means the user has downgraded from a future version
        return False

    version = config_entry.version
    minor_version = config_entry.minor_version

    if version == 1 and minor_version == 1:
        _LOGGER.debug(
            "Migrating Tedee config entry from version %s.%s", version, minor_version
        )
        data = {**config_entry.data, CONF_WEBHOOK_ID: webhook_generate_id()}
        hass.config_entries.async_update_entry(config_entry, data=data, minor_version=2)
        _LOGGER.debug("Migration to version 1.2 successful")
    return True
