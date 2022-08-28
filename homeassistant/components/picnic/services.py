"""Services for the Picnic integration."""
from __future__ import annotations

from typing import Any

from python_picnic_api import PicnicAPI
import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import device_registry
import homeassistant.helpers.config_validation as cv

from .const import (
    ATTR_AMOUNT,
    ATTR_DEVICE_ID,
    ATTR_PRODUCT_ID,
    ATTR_PRODUCT_IDENTIFIERS,
    ATTR_PRODUCT_NAME,
    CONF_API,
    DOMAIN,
    SERVICE_ADD_PRODUCT_TO_CART,
)


class PicnicServiceException(Exception):
    """Exception for Picnic services."""


async def async_register_services(hass: HomeAssistant) -> None:
    """Register services for the Picnic integration, if not registered yet."""

    if hass.services.has_service(DOMAIN, SERVICE_ADD_PRODUCT_TO_CART):
        return

    async def async_add_product_service(call: ServiceCall):
        # Get the picnic API client and call the handler with api client and hass
        api_client = await get_api_client(hass, call.data.get("device_id"))
        await handle_add_product(hass, api_client, call)

    hass.services.async_register(
        DOMAIN,
        SERVICE_ADD_PRODUCT_TO_CART,
        async_add_product_service,
        schema=vol.Schema(
            {
                vol.Optional(ATTR_DEVICE_ID): cv.string,
                vol.Exclusive(
                    ATTR_PRODUCT_ID, ATTR_PRODUCT_IDENTIFIERS
                ): cv.positive_int,
                vol.Exclusive(ATTR_PRODUCT_NAME, ATTR_PRODUCT_IDENTIFIERS): cv.string,
                vol.Optional(ATTR_AMOUNT): vol.All(vol.Coerce(int), vol.Range(min=1)),
            }
        ),
    )


async def get_api_client(
    hass: HomeAssistant, device_id: str | None = None
) -> PicnicAPI:
    """Get the right Picnic API client based on the device id, else get the default one."""
    if device_id is None:
        default_config_id = list(hass.data[DOMAIN].keys())[0]
        return hass.data[DOMAIN][default_config_id][CONF_API]

    # Get device from registry
    registry = device_registry.async_get(hass)
    if not (device := registry.async_get(device_id)):
        raise PicnicServiceException(f"Device with id {device_id} not found!")

    # Get Picnic API client for the config entry id
    try:
        config_entry_id = next(iter(device.config_entries))
        return hass.data[DOMAIN][config_entry_id][CONF_API]
    except StopIteration as error:
        raise PicnicServiceException(
            f"Device with id {device_id} not found!"
        ) from error


async def handle_add_product(
    hass: HomeAssistant, api_client: PicnicAPI, call: ServiceCall
) -> None:
    """Handle the call for the add_product service."""
    product_id = call.data.get("product_id")
    if not product_id:
        product_id = await hass.async_add_executor_job(
            _product_search, api_client, call.data.get("product_name")
        )

    if not product_id:
        raise PicnicServiceException("No product found or no product ID given!")

    await hass.async_add_executor_job(
        api_client.add_product, str(product_id), call.data.get("amount", 1)
    )


def _product_search(api_client: PicnicAPI, product_name: str) -> None | str:
    """Query the api client for the product name."""
    search_result = api_client.search(product_name)

    # Return empty list if the result doesn't contain items
    if not search_result or "items" not in search_result[0]:
        return None

    # Return the first valid result
    for item in search_result[0]["items"]:
        if "name" in item:
            return str(item["id"])

    return None
