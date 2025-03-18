"""The Vegetronix VegeHub integration."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from http import HTTPStatus
from typing import Any

from aiohttp.hdrs import METH_POST
from aiohttp.web import Request, Response
from vegehub import VegeHub, update_data_to_latest_dict

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


@dataclass
class VegeHubData:
    """Define a data class."""

    coordinator: VegeHubCoordinator
    vegehub: VegeHub


# The integration is only set up through the UI (config flow)
async def async_setup_entry(hass: HomeAssistant, entry: VegeHubConfigEntry) -> bool:
    """Set up VegeHub from a config entry."""

    # Register the device in the device registry
    device_mac = entry.data[CONF_MAC]

    assert entry.unique_id

    vegehub = VegeHub(
        entry.data[CONF_IP_ADDRESS],
        device_mac,
        entry.unique_id,
        info=entry.data[CONF_DEVICE],
    )

    # Initialize runtime data
    entry.runtime_data = VegeHubData(
        coordinator=VegeHubCoordinator(hass=hass, config_entry=entry),
        vegehub=vegehub,
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
            get_webhook_handler(
                device_mac, entry.entry_id, entry.runtime_data.coordinator
            ),
            allowed_methods=[METH_POST],
        )

        entry.async_on_unload(
            hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, unregister_webhook)
        )

    # Now add in all the entities for this device.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_create_background_task(
        hass, register_webhook(), "vegehub_register_webhook"
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: VegeHubConfigEntry) -> bool:
    """Unload a VegeHub config entry."""

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
        sensor_data = update_data_to_latest_dict(data)
        if coordinator and sensor_data:
            coordinator.async_set_updated_data(sensor_data)

        return HomeAssistantView.json(result="OK", status_code=HTTPStatus.OK)

    return async_webhook_handler
