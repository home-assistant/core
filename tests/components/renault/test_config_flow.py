"""Test the Renault config flow."""
from homeassistant import config_entries, data_entry_flow
from homeassistant.components.renault.const import (
    CONF_KAMEREON_ACCOUNT_ID,
    DOMAIN,
)
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_USERNAME,
)

from tests.async_mock import patch
from tests.common import MockConfigEntry


async def test_config_flow_single_account(hass):
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {}

    # Failed credentials
    with patch(
        "homeassistant.components.renault.config_flow.PyzeProxy.attempt_login",
        return_value=False,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_USERNAME: "email@test.com", CONF_PASSWORD: "test"},
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
            user_input={CONF_USERNAME: "email@test.com", CONF_PASSWORD: "test"},
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "account_id_1"
    assert result["data"] == {
        CONF_USERNAME: "email@test.com",
        CONF_PASSWORD: "test",
        CONF_KAMEREON_ACCOUNT_ID: "account_id_1",
    }


async def test_config_flow_no_account(hass):
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {}

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
            user_input={CONF_USERNAME: "email@test.com", CONF_PASSWORD: "test"},
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
            user_input={CONF_USERNAME: "email@test.com", CONF_PASSWORD: "test"},
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
        CONF_USERNAME: "email@test.com",
        CONF_PASSWORD: "test",
        CONF_KAMEREON_ACCOUNT_ID: "account_id_2",
    }
