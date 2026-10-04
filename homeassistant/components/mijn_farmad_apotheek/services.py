"""Actions for the Mijn Farmad Apotheek integration."""

from contextlib import suppress
import re
from typing import TYPE_CHECKING, Any

from aiofarmad import (
    CatalogProduct,
    DraftProduct,
    FarmadAuthenticationError,
    FarmadAuthorizationError,
    FarmadCommunicationError,
    FarmadError,
)
import probatio

from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, service

from .const import (
    ATTR_APB,
    ATTR_BASKET_ID,
    ATTR_BRAND,
    ATTR_CNK,
    ATTR_COMMENT,
    ATTR_DESCRIPTION,
    ATTR_IS_ON_PRESCRIPTION,
    ATTR_PACKAGE_QUANTITY,
    ATTR_PHARMACIES,
    ATTR_PRICE,
    ATTR_PRODUCT,
    ATTR_PRODUCTS,
    ATTR_QUANTITY,
    ATTR_QUERY,
    ATTR_STOCK,
    DOMAIN,
    SERVICE_ORDER_MEDICATION,
    SERVICE_SEARCH_MEDICATION,
)

if TYPE_CHECKING:
    from . import FarmadConfigEntry, FarmadData

SEARCH_MEDICATION_SCHEMA = probatio.Schema(
    {
        probatio.Required(ATTR_QUERY): cv.string,
        probatio.Optional(ATTR_APB): cv.string,
    }
)

ORDER_MEDICATION_SCHEMA = probatio.Schema(
    {
        probatio.Required(ATTR_PRODUCT): cv.string,
        probatio.Optional(ATTR_QUANTITY, default=1): probatio.All(
            probatio.Coerce(int), probatio.Range(min=1)
        ),
        probatio.Optional(ATTR_APB): cv.string,
        probatio.Optional(ATTR_COMMENT): cv.string,
    }
)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the actions for the Mijn Farmad Apotheek integration."""
    hass.services.async_register(
        DOMAIN,
        SERVICE_SEARCH_MEDICATION,
        _async_search_medication,
        schema=SEARCH_MEDICATION_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    service.async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_ORDER_MEDICATION,
        _async_order_medication,
        schema=ORDER_MEDICATION_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )


def _resolve_apb(data: FarmadData, apb: str | None) -> str:
    """Return the given apb or the only pharmacy the account is entitled at."""
    if apb is not None:
        return apb
    if not data.pharmacies:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="no_pharmacy"
        )
    if len(data.pharmacies) > 1:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="multiple_pharmacies",
            translation_placeholders={
                ATTR_PHARMACIES: ", ".join(
                    f"{option['label']}: {option['value']}"
                    for option in data.pharmacies
                )
            },
        )
    return data.pharmacies[0]["value"]


def _translate_error(
    err: FarmadError, apb: str, translation_key: str
) -> HomeAssistantError:
    """Return the Home Assistant error for a library error.

    The translation key applies to every error that is no
    authentication or authorization failure.
    """
    if isinstance(err, FarmadAuthenticationError):
        return HomeAssistantError(
            translation_domain=DOMAIN, translation_key="authentication_failed"
        )
    if isinstance(err, FarmadAuthorizationError):
        translation_key = "not_authorized"
    return HomeAssistantError(
        translation_domain=DOMAIN,
        translation_key=translation_key,
        translation_placeholders={ATTR_APB: apb},
    )


def _product_description(product: CatalogProduct) -> str:
    """Return the Dutch description of a catalog product."""
    return product.descriptions.get("nl", "")


def _serialize_product(product: CatalogProduct) -> dict[str, Any]:
    """Convert a catalog product to a plain response dict."""
    return {
        ATTR_CNK: product.cnk,
        ATTR_DESCRIPTION: _product_description(product),
        ATTR_BRAND: product.brand,
        ATTR_PACKAGE_QUANTITY: product.package_quantity,
        ATTR_PRICE: product.price.sales_price if product.price is not None else None,
        ATTR_STOCK: (
            product.stock.total_in_stock if product.stock is not None else None
        ),
        ATTR_IS_ON_PRESCRIPTION: product.is_on_prescription,
    }


async def _async_resolve_product(
    data: FarmadData, apb: str, product_input: str
) -> tuple[str, str]:
    """Resolve a product from the order history or a search by CNK code."""
    if (description := data.products.get(product_input)) is not None:
        return product_input, description
    if re.fullmatch(r"[0-9]{7}", product_input) is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_product",
            translation_placeholders={ATTR_PRODUCT: product_input},
        )
    found = await data.client.async_search_products_in_apb(apb, product_input)
    match = next((product for product in found if product.cnk == product_input), None)
    if match is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="no_search_results",
            translation_placeholders={ATTR_APB: apb, ATTR_QUERY: product_input},
        )
    return match.cnk, _product_description(match)


async def _async_clear_draft(data: FarmadData, apb: str) -> None:
    """Remove the product lines a failed order left in the draft basket.

    The order action only writes to an empty draft, so clearing it
    removes nothing the user added. A failed clear is ignored because
    the next order reports the leftover draft.
    """
    with suppress(FarmadError):
        await data.client.async_clear_draft_basket(apb)


async def _async_write_draft(
    data: FarmadData, apb: str, products: tuple[DraftProduct, ...]
) -> str:
    """Write the products to the empty draft basket and return its id."""
    draft = await data.client.async_get_draft_basket(apb)
    if draft is not None and draft.items:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="draft_not_empty",
            translation_placeholders={ATTR_APB: apb},
        )
    draft_id: str | None
    try:
        if draft is not None and draft.id is not None:
            await data.client.async_update_draft_basket(
                apb, draft.id, products=products
            )
            draft_id = draft.id
        else:
            draft_id = await data.client.async_save_draft_basket(apb, products=products)
    except FarmadError:
        await _async_clear_draft(data, apb)
        raise
    if draft_id is None:
        await _async_clear_draft(data, apb)
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="order_failed",
            translation_placeholders={ATTR_APB: apb},
        )
    return draft_id


async def _async_place_order(
    data: FarmadData,
    apb: str,
    products: tuple[DraftProduct, ...],
    comment: str | None,
) -> str:
    """Submit the products as an order and return the basket id."""
    async with data.lock:
        draft_id = await _async_write_draft(data, apb, products)
        try:
            basket_id = await data.client.async_submit_basket(
                apb, draft_id, products=products, comment=comment
            )
        except FarmadCommunicationError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="order_unconfirmed",
                translation_placeholders={ATTR_APB: apb},
            ) from err
        except FarmadError:
            await _async_clear_draft(data, apb)
            raise
    if basket_id is None:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="order_unconfirmed",
            translation_placeholders={ATTR_APB: apb},
        )
    return basket_id


async def _async_search_medication(call: ServiceCall) -> ServiceResponse:
    """Search the catalog of a Farmad pharmacy."""
    entry: FarmadConfigEntry = service.async_get_config_entry(call.hass, DOMAIN, None)
    data = entry.runtime_data
    apb = _resolve_apb(data, call.data.get(ATTR_APB))
    try:
        products = await data.client.async_search_products_in_apb(
            apb, call.data[ATTR_QUERY], limit=25
        )
    except FarmadError as err:
        raise _translate_error(err, apb, "search_failed") from err
    return {ATTR_PRODUCTS: [_serialize_product(product) for product in products]}


async def _async_order_medication(call: ServiceCall) -> ServiceResponse:
    """Order one product at a Farmad pharmacy."""
    entry: FarmadConfigEntry = service.async_get_config_entry(call.hass, DOMAIN, None)
    data = entry.runtime_data
    apb = _resolve_apb(data, call.data.get(ATTR_APB))
    try:
        cnk, description = await _async_resolve_product(
            data, apb, call.data[ATTR_PRODUCT]
        )
        basket_id = await _async_place_order(
            data,
            apb,
            (DraftProduct(product_cnk=cnk, quantity=call.data[ATTR_QUANTITY]),),
            call.data.get(ATTR_COMMENT),
        )
    except FarmadError as err:
        raise _translate_error(err, apb, "order_failed") from err
    return {ATTR_BASKET_ID: basket_id, ATTR_DESCRIPTION: description}
