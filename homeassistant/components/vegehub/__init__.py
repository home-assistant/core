"""The Vegetronix VegeHub integration."""

from collections.abc import Awaitable, Callable
from http import HTTPStatus
from typing import Any

from aiohttp.hdrs import METH_POST
from aiohttp.web import Request, Response
from vegehub import VegeHub

from homeassistant.components.http import HomeAssistantView
from homeassistant.components.webhook import (
    async_register as webhook_register,
    async_unregister as webhook_unregister,
)
from homeassistant.const import (
    CONF_DEVICE,
    CONF_IP_ADDRESS,
    CONF_MAC,
    CONF_WEBHOOK_ID,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import HomeAssistant

from .const import DOMAIN, NAME, PLATFORMS
from .coordinator import VegeHubConfigEntry, VegeHubCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: VegeHubConfigEntry) -> bool:
    """Set up VegeHub from a config entry."""

    device_mac = entry.data[CONF_MAC]

    assert entry.unique_id

    vegehub = VegeHub(
        entry.data[CONF_IP_ADDRESS],
        device_mac,
        entry.unique_id,
        info=entry.data[CONF_DEVICE],
    )

    # Initialize runtime data
    entry.runtime_data = VegeHubCoordinator(
        hass=hass, config_entry=entry, vegehub=vegehub
    )

    async def unregister_webhook(_: Any) -> None:
        webhook_unregister(hass, entry.data[CONF_WEBHOOK_ID])

    async def register_webhook() -> None:
        webhook_name = f"{NAME} {device_mac}"

        webhook_register(
            hass,
            DOMAIN,
            webhook_name,
            entry.data[CONF_WEBHOOK_ID],
            get_webhook_handler(device_mac, entry.entry_id, entry.runtime_data),
            allowed_methods=[METH_POST],
        )

        entry.async_on_unload(
            hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, unregister_webhook)
        )

    # Now add in all the entities for this device.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    await register_webhook()

    return True


async def async_unload_entry(hass: HomeAssistant, entry: VegeHubConfigEntry) -> bool:
    """Unload a VegeHub config entry."""
    webhook_unregister(hass, entry.data[CONF_WEBHOOK_ID])

    # Unload platforms
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


def get_webhook_handler(
    device_mac: str, entry_id: str, coordinator: VegeHubCoordinator
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
        data = await request.json()

        if coordinator:
            await coordinator.update_from_webhook(data)

        return HomeAssistantView.json(result="OK", status_code=HTTPStatus.OK)

    return async_webhook_handler
