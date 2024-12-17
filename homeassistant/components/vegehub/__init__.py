"""The Vegetronix VegeHub integration."""

from collections.abc import Awaitable, Callable
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
    ATTR_CONFIGURATION_URL,
    ATTR_SW_VERSION,
    CONF_HOST,
    CONF_IP_ADDRESS,
    CONF_MAC,
    CONF_WEBHOOK_ID,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC

from .const import DOMAIN, MANUFACTURER, MODEL, NAME, PLATFORMS

_LOGGER = logging.getLogger(__name__)


# The integration is only set up through the UI (config flow)
async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up VegeHub from a config entry."""

    # Register the device in the device registry
    device_registry = dr.async_get(hass)

    device_mac = entry.data[CONF_MAC]
    device_ip = entry.data[CONF_IP_ADDRESS]

    assert entry.unique_id

    # Register the device
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={(CONNECTION_NETWORK_MAC, device_mac)},
        identifiers={(DOMAIN, device_mac)},
        manufacturer=MANUFACTURER,
        model=MODEL,
        name=entry.data[CONF_HOST],
        sw_version=entry.data[ATTR_SW_VERSION],
        configuration_url=entry.data[ATTR_CONFIGURATION_URL],
    )

    # Initialize runtime data
    entry.runtime_data = VegeHub(device_ip, device_mac, entry.unique_id)

    async def unregister_webhook(_: Any) -> None:
        webhook_unregister(hass, entry.data[CONF_WEBHOOK_ID])

    async def register_webhook() -> None:
        webhook_name = f"{NAME} {device_mac}"

        webhook_register(
            hass,
            DOMAIN,
            webhook_name,
            entry.data[CONF_WEBHOOK_ID],
            get_webhook_handler(device_mac, entry.entry_id),
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


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a VegeHub config entry."""

    # Unload platforms
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


def get_webhook_handler(
    device_mac: str, entry_id: str
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

        # Process sensor data
        if "sensors" in data:
            for sensor in data["sensors"]:
                slot = sensor.get("slot")
                latest_sample = sensor["samples"][-1]
                value = latest_sample["v"]

                # Use the slot number and key to find entity
                entity_id = f"vegehub_{device_mac}_{slot}".lower()

                # Update entity with the new sensor data
                await _update_sensor_entity(hass, value, entity_id, entry_id)

        return HomeAssistantView.json(result="OK", status_code=HTTPStatus.OK)

    return async_webhook_handler


async def _update_sensor_entity(
    hass: HomeAssistant, value: float, entity_id: str, entry_id: str
):
    """Update the corresponding Home Assistant entity with the latest sensor value."""
    entry = hass.config_entries.async_get_entry(entry_id)
    if entry is None:
        _LOGGER.error("Entry %s not found", entry_id)
        return

    # Find the sensor entity and update its state
    entity = None
    try:
        entity = entry.runtime_data.entities.get(entity_id)
        if not entity:
            _LOGGER.error("Sensor entity %s not found", entity_id)
        else:
            await entity.async_update_sensor(value)
    except Exception as e:
        _LOGGER.error("Sensor entity %s not found: %s", entity_id, e)
        raise
