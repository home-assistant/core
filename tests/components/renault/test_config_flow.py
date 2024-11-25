"""Test the Renault config flow."""

from unittest.mock import AsyncMock, PropertyMock, patch

import aiohttp
import pytest
from renault_api.gigya.exceptions import InvalidCredentialsException
from renault_api.kamereon import schemas
from renault_api.renault_account import RenaultAccount

from homeassistant import config_entries
from homeassistant.components.renault.const import (
    CONF_KAMEREON_ACCOUNT_ID,
    CONF_LOCALE,
    DOMAIN,
)
from homeassistant.const import CONF_NAME, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import aiohttp_client

from tests.common import MockConfigEntry, load_fixture

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (Exception, "unknown"),
        (aiohttp.ClientConnectionError, "cannot_connect"),
        (
            InvalidCredentialsException(403042, "invalid loginID or password"),
            "invalid_credentials",
        ),
    ],
)
async def test_config_flow_single_account(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    exception: Exception | type[Exception],
    error: str,
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result["errors"]

    # Raise error
    with patch(
        "renault_api.renault_session.RenaultSession.login",
        side_effect=exception,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_LOCALE: "fr_FR",
                CONF_USERNAME: "email@test.com",
                CONF_PASSWORD: "test",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": error}

    renault_account = AsyncMock()
    type(renault_account).account_id = PropertyMock(return_value="account_id_1")
    renault_account.get_vehicles.return_value = (
        schemas.KamereonVehiclesResponseSchema.loads(
            load_fixture("renault/vehicle_zoe_40.json")
        )
    )

    # Account list single
    with (
        patch("renault_api.renault_session.RenaultSession.login"),
        patch(
            "renault_api.renault_account.RenaultAccount.account_id", return_value="123"
        ),
        patch(
            "renault_api.renault_client.RenaultClient.get_api_accounts",
            return_value=[renault_account],
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_LOCALE: "fr_FR",
                CONF_USERNAME: "email@test.com",
                CONF_PASSWORD: "test",
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "account_id_1"
    assert result["data"][CONF_USERNAME] == "email@test.com"
    assert result["data"][CONF_PASSWORD] == "test"
    assert result["data"][CONF_KAMEREON_ACCOUNT_ID] == "account_id_1"
    assert result["data"][CONF_LOCALE] == "fr_FR"

    assert len(mock_setup_entry.mock_calls) == 1


async def test_config_flow_no_account(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    # Account list empty
    with (
        patch("renault_api.renault_session.RenaultSession.login"),
        patch(
            "renault_api.renault_client.RenaultClient.get_api_accounts",
            return_value=[],
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_LOCALE: "fr_FR",
                CONF_USERNAME: "email@test.com",
                CONF_PASSWORD: "test",
            },
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "kamereon_no_account"

    assert len(mock_setup_entry.mock_calls) == 0


async def test_config_flow_multiple_accounts(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test what happens if multiple Kamereon accounts are available."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    renault_account_1 = RenaultAccount(
        "account_id_1",
        websession=aiohttp_client.async_get_clientsession(hass),
    )
    renault_account_2 = RenaultAccount(
        "account_id_2",
        websession=aiohttp_client.async_get_clientsession(hass),
    )

    # Multiple accounts
    with (
        patch("renault_api.renault_session.RenaultSession.login"),
        patch(
            "renault_api.renault_client.RenaultClient.get_api_accounts",
            return_value=[renault_account_1, renault_account_2],
        ),
        patch("renault_api.renault_account.RenaultAccount.get_vehicles"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_LOCALE: "fr_FR",
                CONF_USERNAME: "email@test.com",
                CONF_PASSWORD: "test",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "kamereon"

    # Account selected
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_KAMEREON_ACCOUNT_ID: "account_id_2"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "account_id_2"
    assert result["data"][CONF_USERNAME] == "email@test.com"
    assert result["data"][CONF_PASSWORD] == "test"
    assert result["data"][CONF_KAMEREON_ACCOUNT_ID] == "account_id_2"
    assert result["data"][CONF_LOCALE] == "fr_FR"

    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("config_entry")
async def test_config_flow_duplicate(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test abort if unique_id configured."""
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    renault_account = RenaultAccount(
        "account_id_1",
        websession=aiohttp_client.async_get_clientsession(hass),
    )
    with (
        patch("renault_api.renault_session.RenaultSession.login"),
        patch(
            "renault_api.renault_client.RenaultClient.get_api_accounts",
            return_value=[renault_account],
        ),
        patch("renault_api.renault_account.RenaultAccount.get_vehicles"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_LOCALE: "fr_FR",
                CONF_USERNAME: "email@test.com",
                CONF_PASSWORD: "test",
            },
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    await hass.async_block_till_done()

    assert len(mock_setup_entry.mock_calls) == 0


async def test_reauth(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Test the start of the config flow."""
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1

    result = await config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["description_placeholders"] == {
        CONF_NAME: "Mock Title",
        CONF_USERNAME: "email@test.com",
    }
    assert result["errors"] == {}

    # Failed credentials
    with patch(
        "renault_api.renault_session.RenaultSession.login",
        side_effect=InvalidCredentialsException(403042, "invalid loginID or password"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_PASSWORD: "any"},
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["description_placeholders"] == {
        CONF_NAME: "Mock Title",
        CONF_USERNAME: "email@test.com",
    }
    assert result2["errors"] == {"base": "invalid_credentials"}

    # Valid credentials
    with patch("renault_api.renault_session.RenaultSession.login"):
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_PASSWORD: "any"},
        )

    assert result3["type"] is FlowResultType.ABORT
    assert result3["reason"] == "reauth_successful"

    assert config_entry.data[CONF_USERNAME] == "email@test.com"
    assert config_entry.data[CONF_PASSWORD] == "any"
