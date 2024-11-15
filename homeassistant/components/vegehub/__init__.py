"""The Vegetronix VegeHub integration."""

from collections.abc import Awaitable, Callable
from http import HTTPStatus
import logging
from typing import Any

from aiohttp.hdrs import METH_POST
from aiohttp.web import Request, Response

from homeassistant.components.http import HomeAssistantView
from homeassistant.components.webhook import (
    async_register as webhook_register,
    async_unregister as webhook_unregister,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_WEBHOOK_ID, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, NAME, PLATFORMS

_LOGGER = logging.getLogger(__name__)

# The integration is only set up through the UI (config flow)
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the VegeHub integration."""
    return True  # For now, we are not using YAML config.


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up VegeHub from a config entry."""

    # Register the device in the device registry
    device_registry = dr.async_get(hass)

    hass.data.setdefault(DOMAIN, {})
    device_mac = str(entry.data.get("mac_address"))

    if entry.unique_id is None:
        new_data = entry.data.copy()
        unique_id = device_mac
        hass.config_entries.async_update_entry(
            entry, data=new_data, unique_id=unique_id
        )

    if device_registry.async_get_device(identifiers={(DOMAIN, entry.entry_id)}):
        _LOGGER.error("Device %s is already registered", entry.entry_id)
        return False

    # Register the device
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, device_mac)},
        identifiers={(DOMAIN, device_mac)},
        manufacturer="Vegetronix",
        model="VegeHub",
        name=entry.data.get("hostname"),
        sw_version=entry.data.get("sw_ver"),
        configuration_url=entry.data.get("config_url"),
    )

    async def unregister_webhook(_: Any) -> None:
        webhook_unregister(hass, entry.data[CONF_WEBHOOK_ID])

    async def register_webhook() -> None:
        webhook_name = "VegeHub"
        if entry.title != NAME:
            webhook_name = f"{NAME} {entry.title}"

        webhook_register(
            hass,
            DOMAIN,
            webhook_name,
            entry.data[CONF_WEBHOOK_ID],
            get_webhook_handler(device_mac),
            allowed_methods=[METH_POST],
        )
        _LOGGER.debug(
            "Registered VegeHub webhook at hass: %s", entry.data.get("webhook_url")
        )

        entry.async_on_unload(
            hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, unregister_webhook)
        )

    entry.async_create_background_task(
        hass, register_webhook(), "vegehub_register_webhook"
    )
    # Now add in all the entities for this device.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a VegeHub config entry."""

    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    # If successful, clean up resources
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)

    return unload_ok


def get_webhook_handler(
    device_mac: str,
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
                await _update_sensor_entity(hass, value, entity_id)

        return HomeAssistantView.json(result="OK", status_code=HTTPStatus.OK)

    return async_webhook_handler


async def _update_sensor_entity(hass: HomeAssistant, value: float, entity_id: str):
    """Update the corresponding Home Assistant entity with the latest sensor value."""

    # Find the sensor entity and update its state
    entity = None
    try:
        if entity_id in hass.data[DOMAIN]:
            entity = hass.data[DOMAIN][entity_id]
        if not entity:
            _LOGGER.error("Sensor entity %s not found", entity_id)
        else:
            await entity.async_update_sensor(value)
    except Exception as e:
        _LOGGER.error("Sensor entity %s not found: %s", entity_id, e)
        raise
