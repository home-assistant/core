"""Test the Renault config flow."""
from homeassistant import config_entries, data_entry_flow
from homeassistant.components.renault.config_flow import (
    DEFAULT_GIGYA_APIKEY,
    DEFAULT_KAMEREON_APIKEY,
)
from homeassistant.components.renault.const import (
    CONF_GIGYA_APIKEY,
    CONF_KAMEREON_ACCOUNT_ID,
    CONF_KAMEREON_APIKEY,
    CONF_LOCALE,
    DOMAIN,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from tests.async_mock import patch


async def test_config_flow_single_account(hass):
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {}

    # Failed API keys
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_GIGYA_APIKEY: DEFAULT_GIGYA_APIKEY,
            CONF_KAMEREON_APIKEY: DEFAULT_KAMEREON_APIKEY,
            CONF_LOCALE: "fr_FR",
        },
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {"base": "invalid_api_keys"}

    # Valid API keys
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_GIGYA_APIKEY: "abc-123456789",
            CONF_KAMEREON_APIKEY: "abc-987654321",
            CONF_LOCALE: "fr_FR",
        },
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {}
    assert result["step_id"] == "credentials"

    # Failed credentials
    with patch(
        "homeassistant.components.renault.config_flow.PyzeProxy.attempt_login",
        return_value=False,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_USERNAME: "email@test.com",
                CONF_PASSWORD: "test",
            },
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {"base": "invalid_credentials"}

    # Account list single
    with patch(
        "homeassistant.components.renault.config_flow.PyzeProxy.attempt_login",
        return_value=True,
    ), patch(
        "homeassistant.components.renault.config_flow.PyzeProxy.get_account_ids",
        return_value=["account_id_1"],
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_USERNAME: "email@test.com",
                CONF_PASSWORD: "test",
            },
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "account_id_1"
    assert result["data"] == {
        CONF_GIGYA_APIKEY: "abc-123456789",
        CONF_KAMEREON_APIKEY: "abc-987654321",
        CONF_USERNAME: "email@test.com",
        CONF_PASSWORD: "test",
        CONF_KAMEREON_ACCOUNT_ID: "account_id_1",
        CONF_LOCALE: "fr_FR",
    }


async def test_config_flow_no_account(hass):
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_GIGYA_APIKEY: "abc-123456789",
            CONF_KAMEREON_APIKEY: "abc-987654321",
            CONF_LOCALE: "fr_FR",
        },
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {}
    assert result["step_id"] == "credentials"

    # Account list empty
    with patch(
        "homeassistant.components.renault.config_flow.PyzeProxy.attempt_login",
        return_value=True,
    ), patch(
        "homeassistant.components.renault.config_flow.PyzeProxy.get_account_ids",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_USERNAME: "email@test.com",
                CONF_PASSWORD: "test",
            },
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "kamereon_no_account"


async def test_config_flow_multiple_accounts(hass):
    """Test what happens if multiple Kamereon accounts are available."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_GIGYA_APIKEY: "abc-123456789",
            CONF_KAMEREON_APIKEY: "abc-987654321",
            CONF_LOCALE: "fr_FR",
        },
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {}
    assert result["step_id"] == "credentials"

    # Multiple accounts
    with patch(
        "homeassistant.components.renault.config_flow.PyzeProxy.attempt_login",
        return_value=True,
    ), patch(
        "homeassistant.components.renault.config_flow.PyzeProxy.get_account_ids",
        return_value=["account_id_1", "account_id_2"],
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
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
    assert result["data"] == {
        CONF_GIGYA_APIKEY: "abc-123456789",
        CONF_KAMEREON_APIKEY: "abc-987654321",
        CONF_USERNAME: "email@test.com",
        CONF_PASSWORD: "test",
        CONF_KAMEREON_ACCOUNT_ID: "account_id_2",
        CONF_LOCALE: "fr_FR",
    }
