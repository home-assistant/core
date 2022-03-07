"""Services for the Picnic integration."""

from python_picnic_api import PicnicAPI
import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import device_registry
import homeassistant.helpers.config_validation as cv

from .const import (
    ATTR_AMOUNT,
    ATTR_DEVICE_ID,
    ATTR_PRODUCT_ID,
    ATTR_PRODUCT_NAME,
    CONF_API,
    DOMAIN,
    PRODUCT_DECORATOR_LABEL,
    PRODUCT_DECORATOR_MAPPING,
    PRODUCT_DECORATOR_PRICE,
    PRODUCT_DECORATOR_VALIDITY,
    SERVICE_ADD_PRODUCT_TO_CART,
    SERVICE_SEARCH_PRODUCT,
)


class PicnicServiceException(Exception):
    """Exception for Picnic services."""


async def async_register_services(hass: HomeAssistant) -> None:
    """Register services for the Picnic integration, if not registered yet."""

    # Register the add_product service
    if not hass.services.has_service(DOMAIN, SERVICE_ADD_PRODUCT_TO_CART):

        async def async_add_product_service(call: ServiceCall):
            # Get the picnic API client and call the handler with api client and hass
            api_client: PicnicAPI = await get_api_client(
                hass, call.data.get("device_id")
            )
            await handle_add_product(hass, api_client, call)

        hass.services.async_register(
            DOMAIN,
            SERVICE_ADD_PRODUCT_TO_CART,
            async_add_product_service,
            schema=vol.Schema(
                {
                    vol.Optional(ATTR_DEVICE_ID): cv.string,
                    vol.Optional(ATTR_PRODUCT_ID): cv.positive_int,
                    vol.Optional(ATTR_PRODUCT_NAME): cv.string,
                    vol.Optional(ATTR_AMOUNT): cv.positive_int,
                }
            ),
        )

    # Register the search service
    if not hass.services.has_service(DOMAIN, SERVICE_SEARCH_PRODUCT):

        async def async_search_product_service(call: ServiceCall):
            # Get the picnic API client and call the handler with api client and hass
            api_client: PicnicAPI = await get_api_client(
                hass, call.data.get("device_id")
            )
            await handle_search(hass, api_client, call)

        hass.services.async_register(
            DOMAIN,
            SERVICE_SEARCH_PRODUCT,
            async_search_product_service,
            schema=vol.Schema(
                {
                    vol.Optional(ATTR_DEVICE_ID): cv.string,
                    vol.Required(ATTR_PRODUCT_NAME): cv.string,
                }
            ),
        )


async def get_api_client(hass, device_id: str = None):
    """Get the right Picnic API client based on the device id, else get the default one."""
    if device_id is None:
        default_config_id = list(hass.data[DOMAIN].keys())[0]
        return hass.data[DOMAIN][default_config_id][CONF_API]

    # Get device from registry
    registry = await device_registry.async_get_registry(hass)
    device = registry.async_get(device_id)

    if device is None:
        raise PicnicServiceException(f"Device with id {device_id} not found!")

    # Get Picnic API client for the config entry id
    try:
        config_entry_id = next(iter(device.config_entries))
        return hass.data[DOMAIN][config_entry_id][CONF_API]
    except (AttributeError, StopIteration, KeyError) as error:
        raise PicnicServiceException(
            f"Device with id {device_id} not found!"
        ) from error


async def handle_add_product(
    hass: HomeAssistant, api_client: PicnicAPI, call: ServiceCall
) -> None:
    """Handle the call for the add_product service."""
    product_id = call.data.get("product_id")
    if not product_id:
        search_results = await hass.async_add_executor_job(
            _product_search, api_client, call.data.get("product_name")
        )
        try:
            product_id = search_results[0]["id"]
        except (IndexError, KeyError, TypeError):
            product_id = None

    if not product_id:
        raise PicnicServiceException("No product found or no product ID given!")

    await hass.async_add_executor_job(
        api_client.add_product, str(product_id), call.data.get("amount", 1)
    )


async def handle_search(
    hass: HomeAssistant, api_client: PicnicAPI, call: ServiceCall
) -> None:
    """Handle the call for the search service."""
    products = await hass.async_add_executor_job(
        _product_search, api_client, call.data.get("product_name")
    )

    products_dict = {p["id"]: p for p in products[:5]}
    hass.bus.async_fire("picnic_search_result", products_dict)


def _product_search(api_client: PicnicAPI, product_name: str):
    """Query the api client for the product name."""
    # Get the search result
    search_result = api_client.search(product_name)

    # Return empty list if the result doesn't contain items
    if not search_result or "items" not in search_result[0]:
        return []

    # Curate a list of Product objects
    products = []
    for item in search_result[0]["items"]:
        if "name" in item:
            # Set the base values
            product = {
                "id": item["id"],
                "name": item["name"],
                "price": item["display_price"] / 100,
                "quantity": item["unit_quantity"],
            }
            # Get the known decorators based on the mapping
            decorators = {
                d["type"]: d[PRODUCT_DECORATOR_MAPPING[d["type"]]]
                for d in item.get("decorators", [])
                if d["type"] in PRODUCT_DECORATOR_MAPPING
            }
            # If a price decorator is present, then the item has a discount. Add this to the product
            if PRODUCT_DECORATOR_PRICE in decorators:
                product["discount_price"] = decorators[PRODUCT_DECORATOR_PRICE] / 100
                product["discount_label"] = decorators.get(
                    PRODUCT_DECORATOR_LABEL, ""
                ).lower()
                product["discount_validity"] = decorators.get(
                    PRODUCT_DECORATOR_VALIDITY
                )

            products += [product]

    return products
