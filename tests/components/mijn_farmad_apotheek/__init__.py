"""Tests for the Mijn Farmad Apotheek integration."""

from typing import Any
from unittest.mock import AsyncMock, Mock

from aiofarmad import (
    AccountMembership,
    BasketLine,
    CatalogProduct,
    CatalogProductPrice,
    CatalogProductStock,
    CustomerBasket,
    FarmadAccount,
)
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.mijn_farmad_apotheek.const import (
    CONF_REFRESH_TOKEN,
    DOMAIN,
)
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import Undefined

API_ACCOUNT_ID = "auth0|farmad-account"
API_ACCOUNT_EMAIL = "test@example.com"
API_ACCOUNT_FULL_NAME = "Test User"
API_ACCESS_TOKEN = "mock-access-token"
API_REFRESH_TOKEN = "mock-refresh-token"
API_APB = "343602"
API_APB_2 = "343605"
API_PRODUCT_CNK = "3093242"
API_PRODUCT_CNK_2 = "3093243"
API_PRODUCT_CNK_LATER = "3093244"
API_PRODUCT_DESCRIPTION = "Dafalgan 500mg"
API_PRODUCT_DESCRIPTION_2 = "Dafalgan 1g"
API_PRODUCT_DESCRIPTION_LATER = "Dafalgan 2g"
API_DRAFT_ID = "mock-draft-id"
API_BASKET_ID = "mock-basket-id"
API_SEARCH_QUERY = "dafalgan"
API_OTP = "123456"
API_OTP_2 = "654321"

ENTRY_DATA = {
    CONF_EMAIL: API_ACCOUNT_EMAIL,
    CONF_ACCESS_TOKEN: API_ACCESS_TOKEN,
    CONF_REFRESH_TOKEN: API_REFRESH_TOKEN,
}

USER_INPUT = {
    CONF_EMAIL: API_ACCOUNT_EMAIL,
    CONF_PASSWORD: "mock-password",
}


def get_mock_account(
    apbs: tuple[str, ...] = (API_APB,), *, account_id: str = API_ACCOUNT_ID
) -> FarmadAccount:
    """Return a Farmad account for the mocked client."""
    return FarmadAccount(
        id=account_id,
        email=API_ACCOUNT_EMAIL,
        first_name="Test",
        last_name="User",
        full_name=API_ACCOUNT_FULL_NAME,
        language="nl",
        blocked=False,
        logins_count=1,
        memberships=tuple(
            AccountMembership(
                user_id=API_ACCOUNT_ID,
                group_id=f"group-{apb}",
                group_name=f"Group {apb}",
                group_description=f"Group of pharmacy {apb}",
                group_owner=apb,
            )
            for apb in apbs
        ),
    )


def get_mock_baskets(
    cnk: str = API_PRODUCT_CNK, description: str = API_PRODUCT_DESCRIPTION
) -> tuple[CustomerBasket, ...]:
    """Return the order history for the mocked client."""
    return (
        CustomerBasket(
            id="mock-history-basket-id",
            customer_patient_id=None,
            customer_patient_name=None,
            state="submitted",
            items=(
                BasketLine(
                    cnk=cnk,
                    description_nl=description,
                    description_fr=description,
                    quantity_ordered=1,
                    unit_price=None,
                ),
            ),
        ),
    )


def get_mock_catalog_product(
    cnk: str = API_PRODUCT_CNK_2, description: str = API_PRODUCT_DESCRIPTION_2
) -> CatalogProduct:
    """Return a catalog product for the mocked client."""
    return CatalogProduct(
        cnk=cnk,
        apb=API_APB,
        descriptions={"nl": description},
        brand="Bristol-Myers Squibb",
        labo="Bristol-Myers Squibb",
        package_code="1612907",
        package_quantity=60.0,
        is_on_prescription=False,
        is_medicine=True,
        is_own_product=False,
        price=CatalogProductPrice(
            sales_price=4.99,
            promo_price_online=None,
            discount_percentage_online=None,
            sales_tva_percentage=None,
            base_price=None,
        ),
        stock=CatalogProductStock(
            availability="IN_STOCK",
            total_in_stock=42,
            quantity_in_robot=None,
            has_robot_location=False,
        ),
    )


def get_mock_client() -> Mock:
    """Return a mock of FarmadClient."""
    client = Mock()
    client.access_token = API_ACCESS_TOKEN
    client.refresh_token = API_REFRESH_TOKEN
    client.async_login = AsyncMock(return_value=None)
    client.async_get_account = AsyncMock(return_value=get_mock_account())
    client.async_get_baskets = AsyncMock(return_value=get_mock_baskets())
    client.async_search_products_in_apb = AsyncMock(
        return_value=(get_mock_catalog_product(),)
    )
    client.async_get_draft_basket = AsyncMock(return_value=None)
    client.async_save_draft_basket = AsyncMock(return_value=API_DRAFT_ID)
    client.async_update_draft_basket = AsyncMock(return_value=API_DRAFT_ID)
    client.async_submit_basket = AsyncMock(return_value=API_BASKET_ID)
    client.async_clear_draft_basket = AsyncMock(return_value=None)
    client.async_close = AsyncMock(return_value=None)
    return client


async def init_integration(
    hass: HomeAssistant,
    *,
    data: dict[str, Any] | Undefined = Undefined,
    entry_id: str | None = None,
) -> MockConfigEntry:
    """Set up the Mijn Farmad Apotheek integration in Home Assistant."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=ENTRY_DATA if data is Undefined else data,
        unique_id=API_ACCOUNT_ID,
        entry_id=entry_id,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry
