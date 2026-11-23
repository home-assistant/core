"""The Watergate integration."""

import asyncio
from collections.abc import Awaitable, Callable
from http import HTTPStatus
import logging

from aiohttp.web import Request, Response
from watergate_local_api import WatergateApiException, WatergateLocalApiClient
from watergate_local_api.models import WebhookEvent
from watergate_local_api.models.webhook_model import (
    AutoShutOffReportData,
    OnlineEvent,
    PowerSupplyChangedEventData,
    TelemetryEventData,
    ValveEventData,
    WifiChangedEventData,
)

from homeassistant.components.http import HomeAssistantView
from homeassistant.components.webhook import (
    async_generate_url,
    async_register,
    async_unregister,
)
from homeassistant.const import CONF_IP_ADDRESS, CONF_WEBHOOK_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import AUTO_SHUT_OFF_EVENT_NAME, DOMAIN
from .coordinator import WatergateConfigEntry, WatergateDataCoordinator

_LOGGER = logging.getLogger(__name__)


CLEAR_WEBHOOK_TIMEOUT = 10

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.EVENT,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.VALVE,
]


async def async_setup_entry(hass: HomeAssistant, entry: WatergateConfigEntry) -> None:
    """Set up Watergate from a config entry."""
    sonic_address = entry.data[CONF_IP_ADDRESS]
    webhook_id = entry.data[CONF_WEBHOOK_ID]

    _LOGGER.debug(
        "Setting up watergate local api integration for device: IP: %s)",
        sonic_address,
    )

    watergate_client = WatergateLocalApiClient(
        base_url=(
            sonic_address
            if sonic_address.startswith("http")
            else f"http://{sonic_address}"
        ),
        session=async_get_clientsession(hass),
    )

    coordinator = WatergateDataCoordinator(hass, entry, watergate_client)
    entry.runtime_data = coordinator

    async_register(
        hass, DOMAIN, "Watergate", webhook_id, get_webhook_handler(coordinator)
    )

    _LOGGER.debug("Registered webhook: %s", webhook_id)

    await coordinator.async_config_entry_first_refresh()

    await watergate_client.async_set_webhook_url(
        async_generate_url(hass, webhook_id, allow_ip=True, prefer_external=False)
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: WatergateConfigEntry) -> None:
    """Unload a config entry."""
    webhook_id = entry.data[CONF_WEBHOOK_ID]
    async_unregister(hass, webhook_id)
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
    # Best effort: an unreachable device must not block the unload.
    try:
        async with asyncio.timeout(CLEAR_WEBHOOK_TIMEOUT):
            await entry.runtime_data.api.async_delete_webhook_url()
    except (WatergateApiException, TimeoutError) as err:
        _LOGGER.debug("Could not clear the webhook URL on the device: %s", err)


def get_webhook_handler(
    coordinator: WatergateDataCoordinator,
) -> Callable[[HomeAssistant, str, Request], Awaitable[Response | None]]:
    """Return webhook handler."""

    async def async_webhook_handler(
        hass: HomeAssistant, webhook_id: str, request: Request
    ) -> Response | None:
        if not request.body_exists:
            return HomeAssistantView.json(
                result="No Body", status_code=HTTPStatus.BAD_REQUEST
            )

        body = await request.json()

        _LOGGER.debug("Received webhook: %s", body)

        data = WebhookEvent.parse_webhook_event(body)

        if isinstance(data, OnlineEvent):
            # The event carries no state, and it may have changed while the
            # device was away, so fetch it instead of guessing.
            await coordinator.async_request_refresh()
            return HomeAssistantView.json(result="OK", status_code=HTTPStatus.OK)

        if not (coordinator_data := coordinator.data):
            pass
        elif isinstance(data, ValveEventData):
            coordinator_data.state.valve_state = data.state
        elif isinstance(data, TelemetryEventData):
            errors = data.errors or []
            coordinator_data.telemetry.flow = (
                data.flow if "flow" not in errors else None
            )
            coordinator_data.telemetry.pressure = (
                data.pressure if "pressure" not in errors else None
            )
            coordinator_data.telemetry.water_temperature = (
                data.temperature if "temperature" not in errors else None
            )
        elif isinstance(data, WifiChangedEventData):
            coordinator_data.networking.ip = data.ip
            coordinator_data.networking.gateway = data.gateway
            coordinator_data.networking.subnet = data.subnet
            coordinator_data.networking.ssid = data.ssid
            coordinator_data.networking.rssi = data.rssi
        elif isinstance(data, PowerSupplyChangedEventData):
            coordinator_data.state.power_supply = data.supply
        elif isinstance(data, AutoShutOffReportData):
            async_dispatcher_send(
                hass, AUTO_SHUT_OFF_EVENT_NAME.format(data.type.lower()), data
            )

        coordinator.async_set_updated_data(coordinator_data)

        if isinstance(data, PowerSupplyChangedEventData):
            # A battery may have been inserted or removed, which changes whether
            # (and what) /power reports.
            await coordinator.async_request_refresh()

        return HomeAssistantView.json(result="OK", status_code=HTTPStatus.OK)

    return async_webhook_handler
