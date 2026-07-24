"""Tests for the National Grid US config flow."""

from unittest.mock import AsyncMock, patch

from py_nationalgrid.exceptions import (
    CannotConnectError,
    InvalidAuthError,
    NationalGridError,
)
import pytest

from homeassistant.components.national_grid_us.const import CONF_ACCOUNT_ID, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import MOCK_ACCOUNT_ID, MOCK_ACCOUNT_ID_2, MOCK_PASSWORD, MOCK_USERNAME

from tests.common import MockConfigEntry

PATCH_CLIENT = (
    "homeassistant.components.national_grid_us.config_flow.NationalGridClient"
)


def _mock_client(
    accounts: list[dict[str, str]],
    service_address: str = "123 Main St, NY",
) -> AsyncMock:
    """Create a mock client that returns the given accounts."""
    client = AsyncMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    client.get_linked_accounts = AsyncMock(return_value=accounts)
    client.get_billing_account = AsyncMock(
        return_value={
            "serviceAddress": {"serviceAddressCompressed": service_address},
        }
    )
    return client


async def test_user_step_shows_form(hass: HomeAssistant) -> None:
    """Test that the user step shows a form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_user_step_single_account(hass: HomeAssistant) -> None:
    """Test user step with a single account creates the entry directly."""
    client = _mock_client([{"billingAccountId": MOCK_ACCOUNT_ID}])
    with patch(PATCH_CLIENT, return_value=client):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={CONF_USERNAME: MOCK_USERNAME, CONF_PASSWORD: MOCK_PASSWORD},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"{MOCK_ACCOUNT_ID} (123 Main St, NY)"
    assert result["data"] == {
        CONF_USERNAME: MOCK_USERNAME,
        CONF_PASSWORD: MOCK_PASSWORD,
        CONF_ACCOUNT_ID: MOCK_ACCOUNT_ID,
    }
    assert result["result"].unique_id == MOCK_ACCOUNT_ID


async def test_user_step_multiple_accounts(hass: HomeAssistant) -> None:
    """Test user step with multiple accounts moves to select_account."""
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
    assert result["step_id"] == "select_account"


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
    """Test user step shows an error and then recovers on a valid retry."""
    client = _mock_client([{"billingAccountId": MOCK_ACCOUNT_ID}])
    client.get_linked_accounts = AsyncMock(side_effect=side_effect)
    with patch(PATCH_CLIENT, return_value=client):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={CONF_USERNAME: MOCK_USERNAME, CONF_PASSWORD: MOCK_PASSWORD},
        )

        assert result["type"] is FlowResultType.FORM
        assert result["errors"]["base"] == expected_error

        # The error clears and a valid retry creates the entry.
        client.get_linked_accounts = AsyncMock(
            return_value=[{"billingAccountId": MOCK_ACCOUNT_ID}]
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_USERNAME: MOCK_USERNAME, CONF_PASSWORD: MOCK_PASSWORD},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_ACCOUNT_ID] == MOCK_ACCOUNT_ID


async def test_user_step_no_accounts_aborts(hass: HomeAssistant) -> None:
    """Test user step aborts when login succeeds but no accounts are returned."""
    client = _mock_client([])
    with patch(PATCH_CLIENT, return_value=client):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={CONF_USERNAME: MOCK_USERNAME, CONF_PASSWORD: MOCK_PASSWORD},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_accounts_found"


def _select_labels(result: dict) -> list[str]:
    """Extract the account-selection option labels from a form result."""
    schema = result["data_schema"].schema
    select = next(iter(schema.values()))
    return [option["label"] for option in select.config["options"]]


async def test_select_account_labels_include_service_address(
    hass: HomeAssistant,
) -> None:
    """Test account selection labels are enriched with the service address."""
    client = _mock_client(
        [
            {"billingAccountId": MOCK_ACCOUNT_ID},
            {"billingAccountId": MOCK_ACCOUNT_ID_2},
        ],
        service_address="123 Main St, NY",
    )
    with patch(PATCH_CLIENT, return_value=client):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={CONF_USERNAME: MOCK_USERNAME, CONF_PASSWORD: MOCK_PASSWORD},
        )

    assert _select_labels(result) == [
        f"Account {MOCK_ACCOUNT_ID} — 123 Main St, NY",
        f"Account {MOCK_ACCOUNT_ID_2} — 123 Main St, NY",
    ]


async def test_select_account_labels_fallback_when_address_unavailable(
    hass: HomeAssistant,
) -> None:
    """Test labels fall back to the account ID when the address lookup fails."""
    client = _mock_client(
        [
            {"billingAccountId": MOCK_ACCOUNT_ID},
            {"billingAccountId": MOCK_ACCOUNT_ID_2},
        ]
    )
    client.get_billing_account = AsyncMock(side_effect=CannotConnectError("Timeout"))
    with patch(PATCH_CLIENT, return_value=client):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={CONF_USERNAME: MOCK_USERNAME, CONF_PASSWORD: MOCK_PASSWORD},
        )

    assert _select_labels(result) == [
        f"Account {MOCK_ACCOUNT_ID}",
        f"Account {MOCK_ACCOUNT_ID_2}",
    ]


async def test_select_account_step(hass: HomeAssistant) -> None:
    """Test selecting an account creates a single entry for that account."""
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
            user_input={CONF_ACCOUNT_ID: MOCK_ACCOUNT_ID_2},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_ACCOUNT_ID] == MOCK_ACCOUNT_ID_2
    assert result["result"].unique_id == MOCK_ACCOUNT_ID_2


async def test_user_step_skips_already_configured_account(
    hass: HomeAssistant,
) -> None:
    """Test an already-configured account is filtered out of the selection.

    With one account already set up, a login that exposes that account plus a
    new one should create the new account's entry directly without prompting.
    """
    existing = MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_ACCOUNT_ID,
        data={
            CONF_USERNAME: MOCK_USERNAME,
            CONF_PASSWORD: MOCK_PASSWORD,
            CONF_ACCOUNT_ID: MOCK_ACCOUNT_ID,
        },
        unique_id=MOCK_ACCOUNT_ID,
    )
    existing.add_to_hass(hass)

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

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_ACCOUNT_ID] == MOCK_ACCOUNT_ID_2


async def test_already_configured(hass: HomeAssistant) -> None:
    """Test that a login exposing only configured accounts aborts."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_ACCOUNT_ID,
        data={
            CONF_USERNAME: MOCK_USERNAME,
            CONF_PASSWORD: MOCK_PASSWORD,
            CONF_ACCOUNT_ID: MOCK_ACCOUNT_ID,
        },
        unique_id=MOCK_ACCOUNT_ID,
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
