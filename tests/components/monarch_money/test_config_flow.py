"""Test the Monarch Money config flow."""

from unittest.mock import AsyncMock

from monarchmoney import LoginFailedException, RequireMFAException

from homeassistant import config_entries
from homeassistant.components.monarch_money.const import CONF_MFA_CODE, DOMAIN
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_form_simple(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_config_api: AsyncMock
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMAIL: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Monarch Money"
    assert result["data"] == {
        CONF_TOKEN: "mocked_token",
    }
    assert result["context"]["unique_id"] == 222260252323873333
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_config_api: AsyncMock
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    # Change the login mock to raise an MFA required error
    mock_config_api.return_value.login.side_effect = LoginFailedException(
        "Invalid Auth"
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMAIL: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    mock_config_api.return_value.login.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMAIL: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Monarch Money"
    assert result["data"] == {
        CONF_TOKEN: "mocked_token",
    }
    assert result["context"]["unique_id"] == 222260252323873333
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_mfa(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_config_api: AsyncMock
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    # Change the login mock to raise an MFA required error
    mock_config_api.return_value.login.side_effect = RequireMFAException("mfa_required")

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMAIL: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "mfa_required"}
    assert result["step_id"] == "user"

    # Add a bad MFA Code response
    mock_config_api.return_value.multi_factor_authenticate.side_effect = KeyError
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_MFA_CODE: "123456",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "bad_mfa"}
    assert result["step_id"] == "user"

    # Use a good MFA Code - Clear mock
    mock_config_api.return_value.multi_factor_authenticate.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_MFA_CODE: "123456",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Monarch Money"
    assert result["data"] == {
        CONF_TOKEN: "mocked_token",
    }
    assert result["result"].unique_id == 222260252323873333

    assert len(mock_setup_entry.mock_calls) == 1
