"""The Vegetronix VegeHub integration."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from http import HTTPStatus
import logging
from typing import Any

from aiohttp.hdrs import METH_POST
from aiohttp.web import Request, Response
from vegehub import VegeHub

from homeassistant.components.http import HomeAssistantView
from homeassistant.components.webhook import (
    async_register as webhook_register,
    async_unregister as webhook_unregister,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_DEVICE,
    CONF_HOST,
    CONF_IP_ADDRESS,
    CONF_MAC,
    CONF_WEBHOOK_ID,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC

from .const import DOMAIN, MANUFACTURER, MODEL, NAME, PLATFORMS
from .coordinator import VegeHubCoordinator

_LOGGER = logging.getLogger(__name__)

type VegeHubConfigEntry = ConfigEntry[VegeHub]


@dataclass
class VegeHubData:
    """Define a data class."""

    coordinator: VegeHubCoordinator
    hub: VegeHub


# The integration is only set up through the UI (config flow)
async def async_setup_entry(hass: HomeAssistant, entry: VegeHubConfigEntry) -> bool:
    """Set up VegeHub from a config entry."""

    # Register the device in the device registry
    device_registry = dr.async_get(hass)

    device_mac = entry.data[CONF_MAC]
    device_ip = entry.data[CONF_IP_ADDRESS]

    assert entry.unique_id

    if entry.data[CONF_DEVICE] is None:
        raise ConfigEntryError("Error: unable to set up device")

    hub = VegeHub(device_ip, device_mac, entry.unique_id, info=entry.data[CONF_DEVICE])

    # Initialize runtime data
    entry.runtime_data = VegeHubData(
        coordinator=VegeHubCoordinator(hass=hass, device_id=entry.unique_id),
        hub=hub,
    )

    # Register the device
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={(CONNECTION_NETWORK_MAC, device_mac)},
        identifiers={(DOMAIN, device_mac)},
        manufacturer=MANUFACTURER,
        model=MODEL,
        name=entry.data[CONF_HOST],
        sw_version=hub.sw_version,
        configuration_url=hub.url,
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

        sensor_data = {}
        # Process sensor data
        if "sensors" in data:
            for sensor in data["sensors"]:
                slot = sensor.get("slot")
                latest_sample = sensor["samples"][-1]
                value = latest_sample["v"]
                entity_id = f"{device_mac}_{slot}".lower()

                # Build a dict of the data we want so that we can pass it to the coordinator
                sensor_data[entity_id] = value

        if coordinator and sensor_data:
            await coordinator.async_update_data(sensor_data)

        return HomeAssistantView.json(result="OK", status_code=HTTPStatus.OK)

    return async_webhook_handler
