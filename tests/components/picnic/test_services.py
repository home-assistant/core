"""Tests for the Picnic services."""
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.picnic import CONF_COUNTRY_CODE, DOMAIN
from homeassistant.components.picnic.const import SERVICE_ADD_PRODUCT_TO_CART
from homeassistant.components.picnic.services import PicnicServiceException
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

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
    picnic_mock.get_user.return_value = auth_data

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
    picnic_api_client.search.return_value = [
        {
            "items": [
                {
                    "id": "2525404",
                    "name": "Best tea",
                    "display_price": 321,
                    "unit_quantity": "big bags",
                },
                {
                    "id": "2525500",
                    "name": "Cheap tea",
                    "display_price": 100,
                    "unit_quantity": "small bags",
                },
            ]
        }
    ]

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

    # Set the search return value and check that the right exception is raised during the service call
    picnic_api_client.search.return_value = []
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

    # Set the search return value and check that the right exception is raised during the service call
    picnic_api_client.search.return_value = [{"items": [{"attr": "test"}]}]
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
    """Test adding a product for a specific Picnic service while multiple are configured."""
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
    with pytest.raises(ValueError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ADD_PRODUCT_TO_CART,
            {"product_id": "5109348572", "config_entry_id": 12345},
            blocking=True,
        )

    # Check that the right method is called on the api
    picnic_api_client.add_product.assert_not_called()
