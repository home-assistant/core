"""Services for the Picnic integration."""

from enum import StrEnum
from typing import cast

import probatio
from python_picnic_api2 import PicnicAPI, PicnicParseError
import requests

from homeassistant.const import CommonServiceArgument
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, service

from .const import ATTR_PRODUCT_IDENTIFIERS, DOMAIN
from .coordinator import PicnicConfigEntry


class PicnicService(StrEnum):
    """Store keys for Picnic services."""

    ADD_PRODUCT = "add_product"


class PicnicServiceArgument(StrEnum):
    """Store keys for Picnic service arguments."""

    PRODUCT_ID = "product_id"
    GTIN = "gtin"
    PRODUCT_NAME = "product_name"
    AMOUNT = "amount"


class PicnicServiceException(Exception):
    """Exception for Picnic services."""


def validate_gtin(value: str) -> str:
    """Validate the format and check digit of a GTIN."""
    if (
        len(value) not in (8, 12, 13, 14)
        or not value.isascii()
        or not value.isdecimal()
    ):
        raise probatio.Invalid("GTIN must contain 8, 12, 13 or 14 digits")

    checksum = sum(
        int(digit) * (1 if index % 2 == 0 else 3)
        for index, digit in enumerate(reversed(value))
    )
    if checksum % 10:
        raise probatio.Invalid("GTIN check digit is invalid")
    return value


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register services for the Picnic integration, if not registered yet."""

    async def async_add_product_service(call: ServiceCall):
        api_client = await get_api_client(
            hass, call.data[CommonServiceArgument.CONFIG_ENTRY_ID]
        )
        await handle_add_product(hass, api_client, call)

    hass.services.async_register(
        DOMAIN,
        PicnicService.ADD_PRODUCT,
        async_add_product_service,
        schema=probatio.Schema(
            {
                probatio.Required(CommonServiceArgument.CONFIG_ENTRY_ID): cv.string,
                probatio.Exclusive(
                    PicnicServiceArgument.PRODUCT_ID, ATTR_PRODUCT_IDENTIFIERS
                ): cv.string,
                probatio.Exclusive(
                    PicnicServiceArgument.PRODUCT_NAME, ATTR_PRODUCT_IDENTIFIERS
                ): cv.string,
                probatio.Exclusive(
                    PicnicServiceArgument.GTIN, ATTR_PRODUCT_IDENTIFIERS
                ): probatio.All(cv.string, validate_gtin),
                probatio.Optional(PicnicServiceArgument.AMOUNT): probatio.All(
                    probatio.Coerce(int), probatio.Range(min=1)
                ),
            }
        ),
    )


async def get_api_client(hass: HomeAssistant, config_entry_id: str) -> PicnicAPI:
    """Get the right Picnic API client based on the config entry id."""
    entry: PicnicConfigEntry = service.async_get_config_entry(
        hass, DOMAIN, config_entry_id
    )
    return entry.runtime_data.picnic_api_client


async def handle_add_product(
    hass: HomeAssistant, api_client: PicnicAPI, call: ServiceCall
) -> None:
    """Handle the call for the add_product service."""
    product_id = call.data.get(PicnicServiceArgument.PRODUCT_ID)
    if gtin := call.data.get(PicnicServiceArgument.GTIN):
        try:
            article = await hass.async_add_executor_job(
                api_client.get_article_by_gtin, gtin
            )
        except (requests.RequestException, PicnicParseError) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="gtin_lookup_failed",
            ) from err

        if article is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="gtin_not_found",
                translation_placeholders={"gtin": gtin},
            )
        product_id = article.id
    elif not product_id:
        product_id = await hass.async_add_executor_job(
            product_search,
            api_client,
            cast(str, call.data[PicnicServiceArgument.PRODUCT_NAME]),
        )

    if not product_id:
        raise PicnicServiceException("No product found or no product ID given!")

    await hass.async_add_executor_job(
        api_client.add_product,
        product_id,
        call.data.get(PicnicServiceArgument.AMOUNT, 1),
    )


def product_search(api_client: PicnicAPI, product_name: str | None) -> str | None:
    """Query the api client for the product name."""
    if product_name is None:
        return None

    search_result = api_client.search(product_name)

    if not search_result or not search_result.items:
        return None

    # Return the first valid result
    for item in search_result.items:
        if item.name:
            return str(item.id)

    return None
