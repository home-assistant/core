"""Test the Mijn Farmad Apotheek integration."""

import asyncio
from unittest.mock import MagicMock

from aiofarmad import (
    BasketItem,
    DraftBasket,
    DraftProduct,
    FarmadAuthenticationError,
    FarmadAuthorizationError,
    FarmadCommunicationError,
    FarmadError,
    FarmadTimeoutError,
)
import probatio
import pytest

from homeassistant.components.mijn_farmad_apotheek.const import (
    ATTR_BASKET_ID,
    ATTR_COMMENT,
    ATTR_DESCRIPTION,
    CONF_REFRESH_TOKEN,
    DOMAIN,
    SERVICE_ORDER_MEDICATION,
    SERVICE_SEARCH_MEDICATION,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import (
    HomeAssistantError,
    ServiceValidationError,
    Unauthorized,
)

from . import (
    API_APB,
    API_APB_2,
    API_BASKET_ID,
    API_DRAFT_ID,
    API_PHARMACY_CITY,
    API_PHARMACY_CITY_2,
    API_PHARMACY_NAME,
    API_PHARMACY_NAME_2,
    API_PRODUCT_CNK,
    API_PRODUCT_CNK_2,
    API_PRODUCT_DESCRIPTION,
    API_PRODUCT_DESCRIPTION_2,
    API_SEARCH_QUERY,
    get_mock_account,
    init_integration,
)

from tests.common import MockUser

ORDER_DATA = {
    "product": API_PRODUCT_CNK,
    "quantity": 1,
    "apb": API_APB,
}

PRODUCTS = (DraftProduct(product_cnk=API_PRODUCT_CNK, quantity=1),)

SEARCH_DATA = {"query": API_SEARCH_QUERY, "apb": API_APB}

SEARCH_RESPONSE = {
    "products": [
        {
            "cnk": API_PRODUCT_CNK_2,
            "description": API_PRODUCT_DESCRIPTION_2,
            "brand": "Bristol-Myers Squibb",
            "package_quantity": 60.0,
            "price": 4.99,
            "stock": 42,
            "is_on_prescription": False,
        }
    ]
}


async def test_setup_entry(hass: HomeAssistant, mock_farmad_client: MagicMock) -> None:
    """Test a config entry sets up and stores the client as runtime data."""
    entry = await init_integration(hass)
    assert entry.state is ConfigEntryState.LOADED
    client = mock_farmad_client.return_value
    assert entry.runtime_data.client is client
    assert entry.runtime_data.pharmacies == [
        {
            "value": API_APB,
            "label": f"{API_PHARMACY_NAME} ({API_PHARMACY_CITY})",
        }
    ]
    assert entry.runtime_data.products == {API_PRODUCT_CNK: API_PRODUCT_DESCRIPTION}
    client.async_get_account.assert_awaited_once()
    client.async_get_organization.assert_awaited_once_with(API_APB)
    client.async_get_baskets.assert_awaited_once_with(API_APB)


async def test_setup_entry_not_ready(
    hass: HomeAssistant, mock_farmad_client: MagicMock
) -> None:
    """Test a config entry retries setup when Farmad cannot be reached."""
    mock_farmad_client.return_value.async_get_account.side_effect = (
        FarmadCommunicationError("mock")
    )
    entry = await init_integration(hass)
    assert entry.state is ConfigEntryState.SETUP_RETRY
    mock_farmad_client.return_value.async_close.assert_awaited_once()


async def test_setup_entry_auth_failed(
    hass: HomeAssistant, mock_farmad_client: MagicMock
) -> None:
    """Test a config entry fails setup without retrying when the session expired."""
    mock_farmad_client.return_value.async_get_account.side_effect = (
        FarmadAuthenticationError("mock")
    )
    entry = await init_integration(hass)
    assert entry.state is ConfigEntryState.SETUP_ERROR
    mock_farmad_client.return_value.async_close.assert_awaited_once()


async def test_setup_entry_not_ready_schema(
    hass: HomeAssistant, mock_farmad_client: MagicMock
) -> None:
    """Test a config entry retries setup when the order history cannot be read."""
    mock_farmad_client.return_value.async_get_baskets.side_effect = (
        FarmadCommunicationError("mock")
    )
    entry = await init_integration(hass)
    assert entry.state is ConfigEntryState.SETUP_RETRY
    mock_farmad_client.return_value.async_close.assert_awaited_once()


async def test_unload_entry(hass: HomeAssistant, mock_farmad_client: MagicMock) -> None:
    """Test a config entry unloads and closes the client."""
    entry = await init_integration(hass)
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED
    mock_farmad_client.return_value.async_close.assert_awaited_once()


async def test_token_rotation(
    hass: HomeAssistant, mock_farmad_client: MagicMock
) -> None:
    """Test rotated tokens are written back to the config entry."""
    entry = await init_integration(hass)
    await mock_farmad_client.call_args.kwargs["on_token_refresh"](
        "new-access-token", "new-refresh-token"
    )
    assert entry.data[CONF_ACCESS_TOKEN] == "new-access-token"
    assert entry.data[CONF_REFRESH_TOKEN] == "new-refresh-token"


async def test_order_medication_requires_admin(
    hass: HomeAssistant,
    hass_read_only_user: MockUser,
    mock_farmad_client: MagicMock,
) -> None:
    """Test ordering requires an admin user."""
    await init_integration(hass)
    client = mock_farmad_client.return_value

    with pytest.raises(Unauthorized):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ORDER_MEDICATION,
            ORDER_DATA,
            blocking=True,
            context=Context(user_id=hass_read_only_user.id),
        )

    client.async_get_draft_basket.assert_not_awaited()


@pytest.mark.usefixtures("mock_farmad_client")
async def test_search_medication_all_users(
    hass: HomeAssistant,
    hass_read_only_user: MockUser,
) -> None:
    """Test searching works for a user without admin access."""
    await init_integration(hass)

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_SEARCH_MEDICATION,
        SEARCH_DATA,
        blocking=True,
        return_response=True,
        context=Context(user_id=hass_read_only_user.id),
    )

    assert response == SEARCH_RESPONSE


async def test_order_medication_from_history(
    hass: HomeAssistant, mock_farmad_client: MagicMock
) -> None:
    """Test ordering a product from the order history places the order."""
    await init_integration(hass)
    client = mock_farmad_client.return_value

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_ORDER_MEDICATION,
        ORDER_DATA,
        blocking=True,
        return_response=True,
    )

    assert response == {
        ATTR_BASKET_ID: API_BASKET_ID,
        ATTR_DESCRIPTION: API_PRODUCT_DESCRIPTION,
    }
    client.async_search_products_in_apb.assert_not_awaited()
    client.async_get_draft_basket.assert_awaited_once_with(API_APB)
    client.async_save_draft_basket.assert_awaited_once_with(API_APB, products=PRODUCTS)
    client.async_update_draft_basket.assert_not_awaited()
    client.async_submit_basket.assert_awaited_once_with(
        API_APB, API_DRAFT_ID, products=PRODUCTS, comment=None
    )


async def test_order_medication_existing_draft(
    hass: HomeAssistant, mock_farmad_client: MagicMock
) -> None:
    """Test ordering replaces the lines of an existing draft."""
    await init_integration(hass)
    client = mock_farmad_client.return_value
    client.async_get_draft_basket.return_value = DraftBasket(
        id=API_DRAFT_ID, comment=None, items=()
    )

    await hass.services.async_call(
        DOMAIN, SERVICE_ORDER_MEDICATION, ORDER_DATA, blocking=True
    )

    client.async_update_draft_basket.assert_awaited_once_with(
        API_APB, API_DRAFT_ID, products=PRODUCTS
    )
    client.async_save_draft_basket.assert_not_awaited()
    client.async_submit_basket.assert_awaited_once_with(
        API_APB, API_DRAFT_ID, products=PRODUCTS, comment=None
    )


@pytest.mark.parametrize(
    "draft_id",
    [
        pytest.param(API_DRAFT_ID, id="with-id"),
        pytest.param(None, id="without-id"),
    ],
)
async def test_order_medication_existing_draft_items(
    hass: HomeAssistant,
    mock_farmad_client: MagicMock,
    draft_id: str | None,
) -> None:
    """Test ordering is rejected when the draft basket has products."""
    await init_integration(hass)
    client = mock_farmad_client.return_value
    client.async_get_draft_basket.return_value = DraftBasket(
        id=draft_id,
        comment=None,
        items=(BasketItem(product_cnk=API_PRODUCT_CNK_2, quantity=1, unit_price=None),),
    )

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN, SERVICE_ORDER_MEDICATION, ORDER_DATA, blocking=True
        )

    assert exc_info.value.translation_key == "draft_not_empty"
    client.async_update_draft_basket.assert_not_awaited()
    client.async_save_draft_basket.assert_not_awaited()
    client.async_submit_basket.assert_not_awaited()


async def test_order_medication_with_comment(
    hass: HomeAssistant, mock_farmad_client: MagicMock
) -> None:
    """Test the comment passes through to the order."""
    await init_integration(hass)
    client = mock_farmad_client.return_value

    await hass.services.async_call(
        DOMAIN,
        SERVICE_ORDER_MEDICATION,
        {**ORDER_DATA, ATTR_COMMENT: "test comment"},
        blocking=True,
    )

    client.async_submit_basket.assert_awaited_once_with(
        API_APB, API_DRAFT_ID, products=PRODUCTS, comment="test comment"
    )


async def test_order_medication_quantity(
    hass: HomeAssistant, mock_farmad_client: MagicMock
) -> None:
    """Test the quantity passes through to the order."""
    await init_integration(hass)
    client = mock_farmad_client.return_value

    await hass.services.async_call(
        DOMAIN,
        SERVICE_ORDER_MEDICATION,
        {**ORDER_DATA, "quantity": 3},
        blocking=True,
    )

    client.async_save_draft_basket.assert_awaited_once_with(
        API_APB, products=(DraftProduct(product_cnk=API_PRODUCT_CNK, quantity=3),)
    )


async def test_order_medication_derived_apb(
    hass: HomeAssistant, mock_farmad_client: MagicMock
) -> None:
    """Test ordering without an apb uses the only entitled pharmacy."""
    await init_integration(hass)
    client = mock_farmad_client.return_value

    await hass.services.async_call(
        DOMAIN,
        SERVICE_ORDER_MEDICATION,
        {"product": API_PRODUCT_CNK},
        blocking=True,
    )

    client.async_save_draft_basket.assert_awaited_once_with(API_APB, products=PRODUCTS)


async def test_order_medication_by_cnk(
    hass: HomeAssistant, mock_farmad_client: MagicMock
) -> None:
    """Test ordering a CNK code outside the list places the order."""
    await init_integration(hass)
    client = mock_farmad_client.return_value

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_ORDER_MEDICATION,
        {"product": API_PRODUCT_CNK_2, "apb": API_APB},
        blocking=True,
        return_response=True,
    )

    client.async_search_products_in_apb.assert_awaited_once_with(
        API_APB, API_PRODUCT_CNK_2
    )
    assert response == {
        ATTR_BASKET_ID: API_BASKET_ID,
        ATTR_DESCRIPTION: API_PRODUCT_DESCRIPTION_2,
    }
    client.async_save_draft_basket.assert_awaited_once_with(
        API_APB,
        products=(DraftProduct(product_cnk=API_PRODUCT_CNK_2, quantity=1),),
    )


async def test_order_medication_no_search_results(
    hass: HomeAssistant, mock_farmad_client: MagicMock
) -> None:
    """Test ordering an unknown CNK code raises a translated error."""
    await init_integration(hass)
    client = mock_farmad_client.return_value
    client.async_search_products_in_apb.return_value = ()

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ORDER_MEDICATION,
            {"product": API_PRODUCT_CNK_2, "apb": API_APB},
            blocking=True,
        )

    assert exc_info.value.translation_key == "no_search_results"
    client.async_submit_basket.assert_not_awaited()


async def test_order_medication_invalid_product(
    hass: HomeAssistant, mock_farmad_client: MagicMock
) -> None:
    """Test a product that is no list entry and no CNK code is rejected."""
    await init_integration(hass)
    client = mock_farmad_client.return_value

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ORDER_MEDICATION,
            {"product": API_SEARCH_QUERY, "apb": API_APB},
            blocking=True,
        )

    assert exc_info.value.translation_key == "invalid_product"
    client.async_search_products_in_apb.assert_not_awaited()
    client.async_submit_basket.assert_not_awaited()


@pytest.mark.parametrize(
    ("method", "side_effect", "translation_key", "clear_count"),
    [
        pytest.param(
            "async_submit_basket",
            FarmadAuthenticationError("mock"),
            "authentication_failed",
            1,
            id="authentication",
        ),
        pytest.param(
            "async_submit_basket",
            FarmadAuthorizationError("mock"),
            "not_authorized",
            1,
            id="authorization",
        ),
        pytest.param(
            "async_submit_basket",
            FarmadError("mock"),
            "order_failed",
            1,
            id="rejected",
        ),
        pytest.param(
            "async_submit_basket",
            FarmadCommunicationError("mock"),
            "order_unconfirmed",
            0,
            id="communication",
        ),
        pytest.param(
            "async_submit_basket",
            FarmadTimeoutError("mock"),
            "order_unconfirmed",
            0,
            id="timeout",
        ),
        pytest.param(
            "async_save_draft_basket",
            FarmadCommunicationError("mock"),
            "order_failed",
            1,
            id="save-draft-communication",
        ),
        pytest.param(
            "async_get_draft_basket",
            FarmadCommunicationError("mock"),
            "order_failed",
            0,
            id="draft-communication",
        ),
    ],
)
async def test_order_medication_errors(
    hass: HomeAssistant,
    mock_farmad_client: MagicMock,
    method: str,
    side_effect: Exception,
    translation_key: str,
    clear_count: int,
) -> None:
    """Test library errors during ordering map to translated Home Assistant errors."""
    await init_integration(hass)
    client = mock_farmad_client.return_value
    getattr(client, method).side_effect = side_effect

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            DOMAIN, SERVICE_ORDER_MEDICATION, ORDER_DATA, blocking=True
        )

    assert exc_info.value.translation_key == translation_key
    assert client.async_clear_draft_basket.await_count == clear_count


async def test_order_medication_clear_draft_fails(
    hass: HomeAssistant, mock_farmad_client: MagicMock
) -> None:
    """Test a failed draft clear does not hide the original order error."""
    await init_integration(hass)
    client = mock_farmad_client.return_value
    client.async_submit_basket.side_effect = FarmadError("mock")
    client.async_clear_draft_basket.side_effect = FarmadCommunicationError("mock")

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            DOMAIN, SERVICE_ORDER_MEDICATION, ORDER_DATA, blocking=True
        )

    assert exc_info.value.translation_key == "order_failed"
    client.async_clear_draft_basket.assert_awaited_once_with(API_APB)


async def test_order_medication_without_draft_id(
    hass: HomeAssistant, mock_farmad_client: MagicMock
) -> None:
    """Test ordering fails and clears the draft when Farmad returns no draft id."""
    await init_integration(hass)
    client = mock_farmad_client.return_value
    client.async_save_draft_basket.return_value = None

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            DOMAIN, SERVICE_ORDER_MEDICATION, ORDER_DATA, blocking=True
        )

    assert exc_info.value.translation_key == "order_failed"
    client.async_submit_basket.assert_not_awaited()
    client.async_clear_draft_basket.assert_awaited_once_with(API_APB)


async def test_order_medication_without_basket_id(
    hass: HomeAssistant, mock_farmad_client: MagicMock
) -> None:
    """Test ordering keeps the draft when Farmad returns no basket id."""
    await init_integration(hass)
    client = mock_farmad_client.return_value
    client.async_submit_basket.return_value = None

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            DOMAIN, SERVICE_ORDER_MEDICATION, ORDER_DATA, blocking=True
        )

    assert exc_info.value.translation_key == "order_unconfirmed"
    client.async_clear_draft_basket.assert_not_awaited()


async def test_order_medication_serialized(
    hass: HomeAssistant, mock_farmad_client: MagicMock
) -> None:
    """Test concurrent orders do not overlap in the draft handling."""
    await init_integration(hass)
    client = mock_farmad_client.return_value
    in_flight = 0
    max_in_flight = 0

    async def track_save(apb: str, *, products: tuple[DraftProduct, ...]) -> str:
        """Mark the start of an order transaction."""
        nonlocal in_flight, max_in_flight
        in_flight += 1
        max_in_flight = max(max_in_flight, in_flight)
        await asyncio.sleep(0)
        return API_DRAFT_ID

    async def track_submit(
        apb: str,
        draft_id: str,
        *,
        products: tuple[DraftProduct, ...],
        comment: str | None,
    ) -> str:
        """Mark the end of an order transaction."""
        nonlocal in_flight
        await asyncio.sleep(0)
        in_flight -= 1
        return API_BASKET_ID

    client.async_save_draft_basket.side_effect = track_save
    client.async_submit_basket.side_effect = track_submit

    await asyncio.gather(
        *(
            asyncio.create_task(
                hass.services.async_call(
                    DOMAIN, SERVICE_ORDER_MEDICATION, ORDER_DATA, blocking=True
                )
            )
            for _ in range(2)
        )
    )

    assert max_in_flight == 1


async def test_order_medication_invalid_quantity(
    hass: HomeAssistant, mock_farmad_client: MagicMock
) -> None:
    """Test a non positive quantity is rejected."""
    await init_integration(hass)

    with pytest.raises(probatio.MultipleInvalid, match="quantity"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ORDER_MEDICATION,
            {"product": API_PRODUCT_CNK, "apb": API_APB, "quantity": 0},
            blocking=True,
        )


async def test_order_medication_after_unload(
    hass: HomeAssistant, mock_farmad_client: MagicMock
) -> None:
    """Test ordering is rejected when the entry is not loaded."""
    entry = await init_integration(hass)
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN, SERVICE_ORDER_MEDICATION, ORDER_DATA, blocking=True
        )


async def test_order_medication_multiple_pharmacies(
    hass: HomeAssistant, mock_farmad_client: MagicMock
) -> None:
    """Test ordering without an apb fails when several pharmacies are entitled."""
    mock_farmad_client.return_value.async_get_account.return_value = get_mock_account(
        (API_APB, API_APB_2)
    )
    await init_integration(hass)
    client = mock_farmad_client.return_value

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ORDER_MEDICATION,
            {"product": API_PRODUCT_CNK},
            blocking=True,
        )

    assert exc_info.value.translation_key == "multiple_pharmacies"
    assert exc_info.value.translation_placeholders is not None
    assert exc_info.value.translation_placeholders["pharmacies"] == (
        f"{API_PHARMACY_NAME} ({API_PHARMACY_CITY}): {API_APB},"
        f" {API_PHARMACY_NAME_2} ({API_PHARMACY_CITY_2}): {API_APB_2}"
    )
    client.async_get_draft_basket.assert_not_awaited()


async def test_order_medication_no_pharmacy(
    hass: HomeAssistant, mock_farmad_client: MagicMock
) -> None:
    """Test ordering without an apb fails when no pharmacy is entitled."""
    mock_farmad_client.return_value.async_get_account.return_value = get_mock_account(
        ()
    )
    await init_integration(hass)

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ORDER_MEDICATION,
            {"product": API_PRODUCT_CNK},
            blocking=True,
        )

    assert exc_info.value.translation_key == "no_pharmacy"


async def test_search_medication(
    hass: HomeAssistant, mock_farmad_client: MagicMock
) -> None:
    """Test searching returns plain products."""
    await init_integration(hass)
    client = mock_farmad_client.return_value

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_SEARCH_MEDICATION,
        SEARCH_DATA,
        blocking=True,
        return_response=True,
    )

    client.async_search_products_in_apb.assert_awaited_once_with(
        API_APB, API_SEARCH_QUERY, limit=25
    )
    assert response == SEARCH_RESPONSE


async def test_search_medication_derived_apb(
    hass: HomeAssistant, mock_farmad_client: MagicMock
) -> None:
    """Test searching without an apb uses the only entitled pharmacy."""
    await init_integration(hass)
    client = mock_farmad_client.return_value

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SEARCH_MEDICATION,
        {"query": API_SEARCH_QUERY},
        blocking=True,
        return_response=True,
    )

    client.async_search_products_in_apb.assert_awaited_once_with(
        API_APB, API_SEARCH_QUERY, limit=25
    )


async def test_search_medication_no_results(
    hass: HomeAssistant, mock_farmad_client: MagicMock
) -> None:
    """Test searching without matches returns an empty product list."""
    await init_integration(hass)
    client = mock_farmad_client.return_value
    client.async_search_products_in_apb.return_value = ()

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_SEARCH_MEDICATION,
        SEARCH_DATA,
        blocking=True,
        return_response=True,
    )

    assert response == {"products": []}


@pytest.mark.parametrize(
    ("side_effect", "translation_key"),
    [
        pytest.param(
            FarmadAuthenticationError("mock"),
            "authentication_failed",
            id="authentication",
        ),
        pytest.param(
            FarmadAuthorizationError("mock"),
            "not_authorized",
            id="authorization",
        ),
        pytest.param(
            FarmadCommunicationError("mock"),
            "search_failed",
            id="communication",
        ),
    ],
)
async def test_search_medication_errors(
    hass: HomeAssistant,
    mock_farmad_client: MagicMock,
    side_effect: Exception,
    translation_key: str,
) -> None:
    """Test library errors map to translated Home Assistant errors."""
    await init_integration(hass)
    mock_farmad_client.return_value.async_search_products_in_apb.side_effect = (
        side_effect
    )

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SEARCH_MEDICATION,
            SEARCH_DATA,
            blocking=True,
            return_response=True,
        )

    assert exc_info.value.translation_key == translation_key


async def test_search_medication_after_unload(
    hass: HomeAssistant, mock_farmad_client: MagicMock
) -> None:
    """Test searching is rejected when the entry is not loaded."""
    entry = await init_integration(hass)
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SEARCH_MEDICATION,
            SEARCH_DATA,
            blocking=True,
            return_response=True,
        )
