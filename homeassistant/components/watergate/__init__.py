"""The Watergate integration."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from http import HTTPStatus
import logging

from watergate_local_api import WatergateLocalApiClient
from watergate_local_api.models import WebhookEvent

from homeassistant.components.http import HomeAssistantView
from homeassistant.components.webhook import Request, Response, async_generate_url
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_IP_ADDRESS, CONF_NAME, CONF_WEBHOOK_ID, Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import WatergateDataCoordinator
from .entity import WatergateConfigEntry, WatergateData

_LOGGER = logging.getLogger(__name__)


PLATFORMS: list[Platform] = [
    Platform.VALVE,
]


async def async_setup_entry(hass: HomeAssistant, entry: WatergateConfigEntry) -> bool:
    """Set up Watergate from a config entry."""
    sonic_name = entry.data[CONF_NAME]
    sonic_address = entry.data[CONF_IP_ADDRESS]
    webhook_id = entry.data[CONF_WEBHOOK_ID]

    _LOGGER.debug(
        "Setting up watergate local api integration for device: %s (IP: %s)",
        sonic_name,
        sonic_address,
    )

    watergate_client = WatergateLocalApiClient(sonic_address)

    coordinator = WatergateDataCoordinator(hass, watergate_client)

    hass.components.webhook.async_unregister(webhook_id)
    hass.components.webhook.async_register(
        DOMAIN, "Watergate", webhook_id, get_webhook_handler(coordinator)
    )

    _LOGGER.debug("Registered webhook: %s", webhook_id)

    await coordinator.async_config_entry_first_refresh()

    await watergate_client.async_set_webhook_url(
        async_generate_url(hass, webhook_id, allow_ip=True)
    )

    entry.runtime_data = WatergateData(watergate_client, coordinator, sonic_name)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


def get_webhook_handler(
    coordinator: WatergateDataCoordinator,
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

        _LOGGER.debug("Received webhook: %s", body)

        data = WebhookEvent.parse_webhook_event(body)

        body_type = body.get("type")

        coordinator_data = coordinator.data
        if body_type == Platform.VALVE and coordinator_data.state:
            coordinator_data.state.valve_state = data.state

        coordinator.async_set_updated_data(coordinator_data)

        return HomeAssistantView.json(result="OK", status_code=HTTPStatus.OK)

    return async_webhook_handler
