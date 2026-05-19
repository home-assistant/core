"""Tests for the National Grid US config flow."""

from unittest.mock import AsyncMock, patch

from py_nationalgrid.exceptions import (
    CannotConnectError,
    InvalidAuthError,
    NationalGridError,
)
import pytest

from homeassistant.components.national_grid_us.const import (
    CONF_SELECTED_ACCOUNTS,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import MOCK_ACCOUNT_ID, MOCK_ACCOUNT_ID_2, MOCK_PASSWORD, MOCK_USERNAME

from tests.common import MockConfigEntry

PATCH_CLIENT = (
    "homeassistant.components.national_grid_us.config_flow.NationalGridClient"
)


def _mock_client(accounts: list[dict[str, str]]) -> AsyncMock:
    """Create a mock client that returns the given accounts."""
    client = AsyncMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    client.get_linked_accounts = AsyncMock(return_value=accounts)
    return client


async def test_user_step_shows_form(hass: HomeAssistant) -> None:
    """Test that the user step shows a form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_user_step_single_account(hass: HomeAssistant) -> None:
    """Test user step with a single account creates entry directly."""
    client = _mock_client([{"billingAccountId": MOCK_ACCOUNT_ID}])
    with patch(PATCH_CLIENT, return_value=client):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={CONF_USERNAME: MOCK_USERNAME, CONF_PASSWORD: MOCK_PASSWORD},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_USERNAME
    assert result["data"][CONF_USERNAME] == MOCK_USERNAME
    assert result["data"][CONF_PASSWORD] == MOCK_PASSWORD
    assert result["data"][CONF_SELECTED_ACCOUNTS] == [MOCK_ACCOUNT_ID]


async def test_user_step_multiple_accounts(hass: HomeAssistant) -> None:
    """Test user step with multiple accounts moves to select_accounts."""
    client = _mock_client(
        [
            {"billingAccountId": MOCK_ACCOUNT_ID},
            {"billingAccountId": MOCK_ACCOUNT_ID_2},
        ]
    )
    with patch(PATCH_CLIENT, return_value=client):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={CONF_USERNAME: MOCK_USERNAME, CONF_PASSWORD: MOCK_PASSWORD},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "select_accounts"


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (InvalidAuthError("Bad creds"), "invalid_auth"),
        (CannotConnectError("Timeout"), "cannot_connect"),
        (NationalGridError("Something broke"), "unknown"),
    ],
)
async def test_user_step_errors(
    hass: HomeAssistant, side_effect: Exception, expected_error: str
) -> None:
    """Test user step with various errors."""
    client = _mock_client([])
    client.get_linked_accounts = AsyncMock(side_effect=side_effect)
    with patch(PATCH_CLIENT, return_value=client):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={CONF_USERNAME: MOCK_USERNAME, CONF_PASSWORD: MOCK_PASSWORD},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == expected_error


async def test_select_accounts_step(hass: HomeAssistant) -> None:
    """Test selecting accounts creates entry."""
    client = _mock_client(
        [
            {"billingAccountId": MOCK_ACCOUNT_ID},
            {"billingAccountId": MOCK_ACCOUNT_ID_2},
        ]
    )
    with patch(PATCH_CLIENT, return_value=client):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={CONF_USERNAME: MOCK_USERNAME, CONF_PASSWORD: MOCK_PASSWORD},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_SELECTED_ACCOUNTS: [MOCK_ACCOUNT_ID]},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_SELECTED_ACCOUNTS] == [MOCK_ACCOUNT_ID]


async def test_select_accounts_none_selected(hass: HomeAssistant) -> None:
    """Test selecting no accounts shows error."""
    client = _mock_client(
        [
            {"billingAccountId": MOCK_ACCOUNT_ID},
            {"billingAccountId": MOCK_ACCOUNT_ID_2},
        ]
    )
    with patch(PATCH_CLIENT, return_value=client):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={CONF_USERNAME: MOCK_USERNAME, CONF_PASSWORD: MOCK_PASSWORD},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_SELECTED_ACCOUNTS: []},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "no_accounts_selected"


async def test_reauth_flow(hass: HomeAssistant) -> None:
    """Test the reauthentication flow."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_USERNAME,
        data={
            CONF_USERNAME: MOCK_USERNAME,
            CONF_PASSWORD: "old_password",
            CONF_SELECTED_ACCOUNTS: [MOCK_ACCOUNT_ID],
        },
        unique_id="testuser_example_com",
    )
    entry.add_to_hass(hass)

    client = _mock_client([{"billingAccountId": MOCK_ACCOUNT_ID}])
    with patch(PATCH_CLIENT, return_value=client):
        result = await entry.start_reauth_flow(hass)
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "reauth_confirm"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_PASSWORD: "new_password"},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_PASSWORD] == "new_password"


async def test_already_configured(hass: HomeAssistant) -> None:
    """Test that duplicate unique_id aborts."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_USERNAME,
        data={
            CONF_USERNAME: MOCK_USERNAME,
            CONF_PASSWORD: MOCK_PASSWORD,
            CONF_SELECTED_ACCOUNTS: [MOCK_ACCOUNT_ID],
        },
        unique_id="testuser_example_com",
    )
    entry.add_to_hass(hass)

    client = _mock_client([{"billingAccountId": MOCK_ACCOUNT_ID}])
    with patch(PATCH_CLIENT, return_value=client):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={CONF_USERNAME: MOCK_USERNAME, CONF_PASSWORD: MOCK_PASSWORD},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (InvalidAuthError("Bad creds"), "invalid_auth"),
        (CannotConnectError("Timeout"), "cannot_connect"),
        (NationalGridError("Something broke"), "unknown"),
    ],
)
async def test_reauth_errors(
    hass: HomeAssistant, side_effect: Exception, expected_error: str
) -> None:
    """Test reauth flow with various errors."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_USERNAME,
        data={
            CONF_USERNAME: MOCK_USERNAME,
            CONF_PASSWORD: "old_password",
            CONF_SELECTED_ACCOUNTS: [MOCK_ACCOUNT_ID],
        },
        unique_id="testuser_example_com",
    )
    entry.add_to_hass(hass)

    client = _mock_client([])
    client.get_linked_accounts = AsyncMock(side_effect=side_effect)
    with patch(PATCH_CLIENT, return_value=client):
        result = await entry.start_reauth_flow(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_PASSWORD: "new_password"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == expected_error
