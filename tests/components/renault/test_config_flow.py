"""Test the Renault config flow."""
from unittest.mock import AsyncMock, PropertyMock, patch

from renault_api.gigya.exceptions import InvalidCredentialsException
from renault_api.kamereon import schemas

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.renault.const import (
    CONF_KAMEREON_ACCOUNT_ID,
    CONF_LOCALE,
    DOMAIN,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import load_fixture


async def test_config_flow_single_account(hass: HomeAssistant):
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {}

    # Failed credentials
    with patch(
        "renault_api.renault_session.RenaultSession.login",
        side_effect=InvalidCredentialsException(403042, "invalid loginID or password"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_LOCALE: "fr_FR",
                CONF_USERNAME: "email@test.com",
                CONF_PASSWORD: "test",
            },
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {"base": "invalid_credentials"}

    renault_account = AsyncMock()
    type(renault_account).account_id = PropertyMock(return_value="account_id_1")
    renault_account.get_vehicles.return_value = (
        schemas.KamereonVehiclesResponseSchema.loads(
            load_fixture("renault/vehicle_zoe_40.json")
        )
    )

    # Account list single
    with patch("renault_api.renault_session.RenaultSession.login"), patch(
        "renault_api.renault_account.RenaultAccount.account_id", return_value="123"
    ), patch(
        "renault_api.renault_client.RenaultClient.get_api_accounts",
        return_value=[renault_account],
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_LOCALE: "fr_FR",
                CONF_USERNAME: "email@test.com",
                CONF_PASSWORD: "test",
            },
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "account_id_1"
    assert result["data"][CONF_USERNAME] == "email@test.com"
    assert result["data"][CONF_PASSWORD] == "test"
    assert result["data"][CONF_KAMEREON_ACCOUNT_ID] == "account_id_1"
    assert result["data"][CONF_LOCALE] == "fr_FR"


async def test_config_flow_no_account(hass: HomeAssistant):
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {}

    # Account list empty
    with patch("renault_api.renault_session.RenaultSession.login"), patch(
        "homeassistant.components.renault.config_flow.RenaultHub.get_account_ids",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_LOCALE: "fr_FR",
                CONF_USERNAME: "email@test.com",
                CONF_PASSWORD: "test",
            },
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "kamereon_no_account"


async def test_config_flow_multiple_accounts(hass: HomeAssistant):
    """Test what happens if multiple Kamereon accounts are available."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {}

    # Multiple accounts
    with patch("renault_api.renault_session.RenaultSession.login"), patch(
        "homeassistant.components.renault.config_flow.RenaultHub.get_account_ids",
        return_value=["account_id_1", "account_id_2"],
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_LOCALE: "fr_FR",
                CONF_USERNAME: "email@test.com",
                CONF_PASSWORD: "test",
            },
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "kamereon"

    # Account selected
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_KAMEREON_ACCOUNT_ID: "account_id_2"},
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "account_id_2"
    assert result["data"][CONF_USERNAME] == "email@test.com"
    assert result["data"][CONF_PASSWORD] == "test"
    assert result["data"][CONF_KAMEREON_ACCOUNT_ID] == "account_id_2"
    assert result["data"][CONF_LOCALE] == "fr_FR"
