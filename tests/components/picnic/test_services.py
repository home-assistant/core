"""Tests for the Picnic services."""

from unittest.mock import MagicMock, patch

import probatio
import pytest
from pytest_homeassistant.common import MockConfigEntry
from python_picnic_api2 import PicnicParseError
from python_picnic_api2.models import Article, SearchResult, SearchResultItem, User
import requests

from homeassistant.components.picnic import CONF_COUNTRY_CODE, DOMAIN
from homeassistant.components.picnic.const import SERVICE_ADD_PRODUCT_TO_CART
from homeassistant.components.picnic.services import PicnicServiceException
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.script import Script, async_validate_actions_config

UNIQUE_ID = "295-6y3-1nf4"


def create_picnic_api_client(unique_id):
    """Create PicnicAPI mock with set response data."""
    auth_token = "af3wh738j3fa28l9fa23lhiufahu7l"
    auth_data = {
        "user_id": unique_id,
        "address": {
            "street": "Teststreet",
            "house_number": 123,
            "house_number_ext": "b",
        },
    }
    picnic_mock = MagicMock()
    picnic_mock.session.auth_token = auth_token
    picnic_mock.get_user.return_value = User.from_api(auth_data)

    return picnic_mock


async def create_picnic_config_entry(hass: HomeAssistant, unique_id):
    """Create a Picnic config entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ACCESS_TOKEN: "x-original-picnic-auth-token",
            CONF_COUNTRY_CODE: "NL",
        },
        unique_id=unique_id,
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    return config_entry


@pytest.fixture
def picnic_api_client():
    """Return the default picnic api client."""
    with patch(
        "homeassistant.components.picnic.create_picnic_client"
    ) as create_picnic_client_mock:
        picnic_client_mock = create_picnic_api_client(UNIQUE_ID)
        create_picnic_client_mock.return_value = picnic_client_mock

        yield picnic_client_mock


@pytest.fixture
async def picnic_config_entry(hass: HomeAssistant):
    """Generate the default Picnic config entry."""
    return await create_picnic_config_entry(hass, UNIQUE_ID)


async def test_add_product_using_id(
    hass: HomeAssistant,
    picnic_api_client: MagicMock,
    picnic_config_entry: MockConfigEntry,
) -> None:
    """Test adding a product by id."""
    await hass.services.async_call(
        DOMAIN,
        SERVICE_ADD_PRODUCT_TO_CART,
        {
            "config_entry_id": picnic_config_entry.entry_id,
            "product_id": "5109348572",
            "amount": 3,
        },
        blocking=True,
    )

    # Check that the right method is called on the api
    picnic_api_client.add_product.assert_called_with("5109348572", 3)


async def test_add_product_using_name(
    hass: HomeAssistant,
    picnic_api_client: MagicMock,
    picnic_config_entry: MockConfigEntry,
) -> None:
    """Test adding a product by name."""

    # Set the return value of the search api endpoint
    picnic_api_client.search.return_value = SearchResult(
        items=[
            SearchResultItem(
                id="2525404",
                name="Best tea",
                display_price=321,
                unit_quantity="big bags",
            ),
            SearchResultItem(
                id="2525500",
                name="Cheap tea",
                display_price=100,
                unit_quantity="small bags",
            ),
        ]
    )

    await hass.services.async_call(
        DOMAIN,
        SERVICE_ADD_PRODUCT_TO_CART,
        {"config_entry_id": picnic_config_entry.entry_id, "product_name": "Tea"},
        blocking=True,
    )

    # Check that the right method is called on the api
    picnic_api_client.add_product.assert_called_with("2525404", 1)


async def test_add_product_using_name_no_results(
    hass: HomeAssistant,
    picnic_api_client: MagicMock,
    picnic_config_entry: MockConfigEntry,
) -> None:
    """Test adding a product by name that can't be found."""

    # Set the search return value and check that the right exception
    # is raised during the service call
    picnic_api_client.search.return_value = SearchResult(items=[])
    with pytest.raises(PicnicServiceException):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ADD_PRODUCT_TO_CART,
            {
                "config_entry_id": picnic_config_entry.entry_id,
                "product_name": "Random non existing product",
            },
            blocking=True,
        )


async def test_add_product_using_name_no_named_results(
    hass: HomeAssistant,
    picnic_api_client: MagicMock,
    picnic_config_entry: MockConfigEntry,
) -> None:
    """Test adding a product by name for which no named results are returned."""

    # Set the search return value and check that the right exception
    # is raised during the service call
    picnic_api_client.search.return_value = SearchResult(
        items=[SearchResultItem(id="999")]
    )
    with pytest.raises(PicnicServiceException):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ADD_PRODUCT_TO_CART,
            {
                "config_entry_id": picnic_config_entry.entry_id,
                "product_name": "Random product",
            },
            blocking=True,
        )


async def test_add_product_multiple_config_entries(
    hass: HomeAssistant,
    picnic_api_client: MagicMock,
    picnic_config_entry: MockConfigEntry,
) -> None:
    """Test adding a product while multiple services are configured."""
    with patch(
        "homeassistant.components.picnic.create_picnic_client"
    ) as create_picnic_client_mock:
        picnic_api_client_2 = create_picnic_api_client("3fj9-9gju-236")
        create_picnic_client_mock.return_value = picnic_api_client_2
        picnic_config_entry_2 = await create_picnic_config_entry(hass, "3fj9-9gju-236")

    await hass.services.async_call(
        DOMAIN,
        SERVICE_ADD_PRODUCT_TO_CART,
        {"product_id": "5109348572", "config_entry_id": picnic_config_entry_2.entry_id},
        blocking=True,
    )

    # Check that the right method is called on the api
    picnic_api_client.add_product.assert_not_called()
    picnic_api_client_2.add_product.assert_called_with("5109348572", 1)


async def test_add_product_device_doesnt_exist(
    hass: HomeAssistant,
    picnic_api_client: MagicMock,
    picnic_config_entry: MockConfigEntry,
) -> None:
    """Test adding a product for a specific Picnic service, which doesn't exist."""
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ADD_PRODUCT_TO_CART,
            {"product_id": "5109348572", "config_entry_id": 12345},
            blocking=True,
        )

    # Check that the right method is called on the api
    picnic_api_client.add_product.assert_not_called()


@pytest.mark.parametrize(
    "gtin",
    [
        pytest.param("96385074", id="gtin-8"),
        pytest.param("036000291452", id="gtin-12-leading-zero"),
        pytest.param("8720326041724", id="gtin-13"),
        pytest.param("08720326041724", id="gtin-14-leading-zero"),
        pytest.param(8720326041724, id="numeric-input"),
    ],
)
@pytest.mark.parametrize("amount", [1, 3])
async def test_add_product_using_gtin(
    hass: HomeAssistant,
    picnic_api_client: MagicMock,
    picnic_config_entry: MockConfigEntry,
    gtin: str | int,
    amount: int,
) -> None:
    """Resolve a GTIN before adding the requested quantity."""
    picnic_api_client.get_article_by_gtin.return_value = Article(id="s1011534")

    await hass.services.async_call(
        DOMAIN,
        SERVICE_ADD_PRODUCT_TO_CART,
        {
            "config_entry_id": picnic_config_entry.entry_id,
            "gtin": gtin,
            "amount": amount,
        },
        blocking=True,
    )

    picnic_api_client.get_article_by_gtin.assert_called_once_with(str(gtin))
    picnic_api_client.add_product.assert_called_once_with("s1011534", amount)
    picnic_api_client.search.assert_not_called()


@pytest.mark.parametrize("gtin", ["8720326041724", "08720326041724"])
async def test_add_product_using_gtin_template(
    hass: HomeAssistant,
    picnic_api_client: MagicMock,
    picnic_config_entry: MockConfigEntry,
    gtin: str,
) -> None:
    """Accept scalar templates and preserve leading zeroes."""
    picnic_api_client.get_article_by_gtin.return_value = Article(id="s1011534")
    sequence = await async_validate_actions_config(
        hass,
        cv.SCRIPT_SCHEMA(
            [
                {
                    "action": "picnic.add_product",
                    "data": {
                        "config_entry_id": picnic_config_entry.entry_id,
                        "gtin": "{{ barcode }}",
                    },
                }
            ]
        ),
    )
    script = Script(hass, sequence, "Add a Picnic product", DOMAIN)

    await script.async_run({"barcode": gtin}, Context())

    picnic_api_client.get_article_by_gtin.assert_called_once_with(gtin)
    picnic_api_client.add_product.assert_called_once_with("s1011534", 1)


async def test_add_product_using_unknown_gtin(
    hass: HomeAssistant,
    picnic_api_client: MagicMock,
    picnic_config_entry: MockConfigEntry,
) -> None:
    """An unknown GTIN must not fall back to a name search or add a product."""
    picnic_api_client.get_article_by_gtin.return_value = None

    with pytest.raises(ServiceValidationError, match="No Picnic product found") as err:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ADD_PRODUCT_TO_CART,
            {
                "config_entry_id": picnic_config_entry.entry_id,
                "gtin": "5000112678468",
            },
            blocking=True,
        )

    assert err.value.translation_key == "gtin_not_found"
    assert err.value.translation_placeholders == {"gtin": "5000112678468"}
    picnic_api_client.add_product.assert_not_called()
    picnic_api_client.search.assert_not_called()


@pytest.mark.parametrize(
    "exception",
    [
        pytest.param(requests.Timeout(), id="timeout"),
        pytest.param(requests.ConnectionError(), id="connection-error"),
        pytest.param(requests.HTTPError(), id="http-error"),
        pytest.param(PicnicParseError("Invalid article response"), id="parse-error"),
    ],
)
async def test_add_product_gtin_lookup_failure(
    hass: HomeAssistant,
    picnic_api_client: MagicMock,
    picnic_config_entry: MockConfigEntry,
    exception: Exception,
) -> None:
    """Report lookup errors without adding a product."""
    picnic_api_client.get_article_by_gtin.side_effect = exception

    with pytest.raises(HomeAssistantError, match="Unable to look up") as err:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ADD_PRODUCT_TO_CART,
            {
                "config_entry_id": picnic_config_entry.entry_id,
                "gtin": "8720326041724",
            },
            blocking=True,
        )

    assert err.value.translation_key == "gtin_lookup_failed"
    picnic_api_client.add_product.assert_not_called()
    picnic_api_client.search.assert_not_called()


@pytest.mark.parametrize(
    "gtin",
    [
        pytest.param("", id="empty"),
        pytest.param("123", id="wrong-length"),
        pytest.param("8720326041725", id="invalid-check-digit"),
        pytest.param("872032604172x", id="non-digit"),
        pytest.param("８７２０３２６０４１７２４", id="non-ascii"),
        pytest.param("8720326041724 ", id="whitespace"),
        pytest.param(None, id="null"),
        pytest.param(True, id="boolean"),
        pytest.param(8720326041724.0, id="float"),
        pytest.param(["8720326041724"], id="list"),
    ],
)
async def test_add_product_using_invalid_gtin(
    hass: HomeAssistant,
    picnic_api_client: MagicMock,
    picnic_config_entry: MockConfigEntry,
    gtin: object,
) -> None:
    """Reject invalid input before calling the API."""
    with pytest.raises(probatio.Invalid):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ADD_PRODUCT_TO_CART,
            {
                "config_entry_id": picnic_config_entry.entry_id,
                "gtin": gtin,
            },
            blocking=True,
        )

    picnic_api_client.get_article_by_gtin.assert_not_called()
    picnic_api_client.add_product.assert_not_called()


@pytest.mark.parametrize(
    "identifiers",
    [
        pytest.param(
            {"gtin": "8720326041724", "product_id": "s1011534"}, id="gtin-and-id"
        ),
        pytest.param(
            {"gtin": "8720326041724", "product_name": "Butter"}, id="gtin-and-name"
        ),
        pytest.param(
            {
                "gtin": "8720326041724",
                "product_id": "s1011534",
                "product_name": "Butter",
            },
            id="all-identifiers",
        ),
    ],
)
async def test_add_product_gtin_excludes_other_identifiers(
    hass: HomeAssistant,
    picnic_api_client: MagicMock,
    picnic_config_entry: MockConfigEntry,
    identifiers: dict[str, str],
) -> None:
    """GTIN is mutually exclusive with the existing product identifiers."""
    with pytest.raises(probatio.Invalid):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ADD_PRODUCT_TO_CART,
            {"config_entry_id": picnic_config_entry.entry_id, **identifiers},
            blocking=True,
        )

    picnic_api_client.get_article_by_gtin.assert_not_called()
    picnic_api_client.add_product.assert_not_called()
    picnic_api_client.search.assert_not_called()


async def test_add_product_using_gtin_multiple_config_entries(
    hass: HomeAssistant,
    picnic_api_client: MagicMock,
    picnic_config_entry: MockConfigEntry,
) -> None:
    """Resolve and add through the selected account."""
    with patch(
        "homeassistant.components.picnic.create_picnic_client"
    ) as create_picnic_client_mock:
        other_client = create_picnic_api_client("other-picnic-account")
        other_client.get_article_by_gtin.return_value = Article(id="s1011534")
        create_picnic_client_mock.return_value = other_client
        other_entry = await create_picnic_config_entry(hass, "other-picnic-account")

    await hass.services.async_call(
        DOMAIN,
        SERVICE_ADD_PRODUCT_TO_CART,
        {"config_entry_id": other_entry.entry_id, "gtin": "8720326041724"},
        blocking=True,
    )

    picnic_api_client.get_article_by_gtin.assert_not_called()
    picnic_api_client.add_product.assert_not_called()
    other_client.get_article_by_gtin.assert_called_once_with("8720326041724")
    other_client.add_product.assert_called_once_with("s1011534", 1)
