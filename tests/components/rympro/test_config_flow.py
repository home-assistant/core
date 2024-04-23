"""Test the Read Your Meter Pro config flow."""

from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.rympro.config_flow import (
    CannotConnectError,
    UnauthorizedError,
)
from homeassistant.components.rympro.const import DOMAIN
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, CONF_TOKEN, CONF_UNIQUE_ID
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

TEST_DATA = {
    CONF_EMAIL: "test-email",
    CONF_PASSWORD: "test-password",
    CONF_TOKEN: "test-token",
    CONF_UNIQUE_ID: "test-account-number",
}


@pytest.fixture
def config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Create a mock config entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=TEST_DATA,
        unique_id=TEST_DATA[CONF_UNIQUE_ID],
    )
    config_entry.add_to_hass(hass)
    return config_entry


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    with (
        patch(
            "homeassistant.components.rympro.config_flow.RymPro.login",
            return_value="test-token",
        ),
        patch(
            "homeassistant.components.rympro.config_flow.RymPro.account_info",
            return_value={"accountNumber": TEST_DATA[CONF_UNIQUE_ID]},
        ),
        patch(
            "homeassistant.components.rympro.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_EMAIL: TEST_DATA[CONF_EMAIL],
                CONF_PASSWORD: TEST_DATA[CONF_PASSWORD],
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == TEST_DATA[CONF_EMAIL]
    assert result2["data"] == TEST_DATA
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (UnauthorizedError, "invalid_auth"),
        (CannotConnectError, "cannot_connect"),
        (Exception, "unknown"),
    ],
)
async def test_login_error(hass: HomeAssistant, exception, error) -> None:
    """Test we handle config flow errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(
        "homeassistant.components.rympro.config_flow.RymPro.login",
        side_effect=exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_EMAIL: TEST_DATA[CONF_EMAIL],
                CONF_PASSWORD: TEST_DATA[CONF_PASSWORD],
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": error}

    with (
        patch(
            "homeassistant.components.rympro.config_flow.RymPro.login",
            return_value="test-token",
        ),
        patch(
            "homeassistant.components.rympro.config_flow.RymPro.account_info",
            return_value={"accountNumber": TEST_DATA[CONF_UNIQUE_ID]},
        ),
        patch(
            "homeassistant.components.rympro.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                CONF_EMAIL: TEST_DATA[CONF_EMAIL],
                CONF_PASSWORD: TEST_DATA[CONF_PASSWORD],
            },
        )
        await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["title"] == TEST_DATA[CONF_EMAIL]
    assert result3["data"] == TEST_DATA
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_already_exists(hass: HomeAssistant, config_entry) -> None:
    """Test that a flow with an existing account aborts."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with (
        patch(
            "homeassistant.components.rympro.config_flow.RymPro.login",
            return_value="test-token",
        ),
        patch(
            "homeassistant.components.rympro.config_flow.RymPro.account_info",
            return_value={"accountNumber": TEST_DATA[CONF_UNIQUE_ID]},
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_EMAIL: TEST_DATA[CONF_EMAIL],
                CONF_PASSWORD: TEST_DATA[CONF_PASSWORD],
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


async def test_form_reauth(hass: HomeAssistant, config_entry) -> None:
    """Test reauthentication."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": config_entry.entry_id,
        },
        data=config_entry.data,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    with (
        patch(
            "homeassistant.components.rympro.config_flow.RymPro.login",
            return_value="test-token",
        ),
        patch(
            "homeassistant.components.rympro.config_flow.RymPro.account_info",
            return_value={"accountNumber": TEST_DATA[CONF_UNIQUE_ID]},
        ),
        patch(
            "homeassistant.components.rympro.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_EMAIL: TEST_DATA[CONF_EMAIL],
                CONF_PASSWORD: "new_password",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"
    assert config_entry.data[CONF_PASSWORD] == "new_password"
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_reauth_with_new_account(hass: HomeAssistant, config_entry) -> None:
    """Test reauthentication with new account."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": config_entry.entry_id,
        },
        data=config_entry.data,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    with (
        patch(
            "homeassistant.components.rympro.config_flow.RymPro.login",
            return_value="test-token",
        ),
        patch(
            "homeassistant.components.rympro.config_flow.RymPro.account_info",
            return_value={"accountNumber": "new-account-number"},
        ),
        patch(
            "homeassistant.components.rympro.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_EMAIL: TEST_DATA[CONF_EMAIL],
                CONF_PASSWORD: TEST_DATA[CONF_PASSWORD],
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"
    assert config_entry.data[CONF_UNIQUE_ID] == "new-account-number"
    assert config_entry.unique_id == "new-account-number"
    assert len(mock_setup_entry.mock_calls) == 1
