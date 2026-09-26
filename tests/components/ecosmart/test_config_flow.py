"""Test the ecosmart config flow."""

from dataclasses import replace
from unittest.mock import AsyncMock

from aioecosmart import (
    EcosmartAuthError,
    EcosmartConnectionError,
    EcosmartRateLimitError,
)
import pytest

from homeassistant.components.ecosmart.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import TEST_ACCOUNT_REF, TEST_API_KEY, load_identity

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")

USER_INPUT = {CONF_API_KEY: TEST_API_KEY}


async def test_user_flow(hass: HomeAssistant, mock_ecosmart_client: AsyncMock) -> None:
    """Test the happy path creates an entry keyed on the account reference."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result["errors"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "redacted"
    assert result["data"] == USER_INPUT
    assert result["result"].unique_id == TEST_ACCOUNT_REF


async def test_user_flow_unlabelled_key(
    hass: HomeAssistant, mock_ecosmart_client: AsyncMock
) -> None:
    """Test a key with no label falls back to the integration name."""
    mock_ecosmart_client.me.return_value = replace(load_identity(), label="")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "ecosmart"


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (EcosmartAuthError("nope"), "invalid_auth"),
        (EcosmartConnectionError("offline"), "cannot_connect"),
        (EcosmartRateLimitError("slow down", retry_after=30), "rate_limited"),
        (Exception("boom"), "unknown"),
    ],
)
async def test_user_flow_errors_then_recovers(
    hass: HomeAssistant,
    mock_ecosmart_client: AsyncMock,
    side_effect: Exception,
    error: str,
) -> None:
    """Test each failure shows its error and the flow still finishes afterwards."""
    mock_ecosmart_client.me.side_effect = side_effect

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_ecosmart_client.me.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == TEST_ACCOUNT_REF


async def test_user_flow_no_icps_then_recovers(
    hass: HomeAssistant, mock_ecosmart_client: AsyncMock
) -> None:
    """Test a key minted before switch-in is rejected, not accepted empty."""
    mock_ecosmart_client.me.return_value = load_identity("me_no_icps.json")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_icps"}

    mock_ecosmart_client.me.return_value = load_identity()
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == TEST_ACCOUNT_REF


async def test_duplicate_account_aborts(
    hass: HomeAssistant,
    mock_ecosmart_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a second key for the same account aborts."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
