"""Test the Aqvify config flow."""

from unittest.mock import AsyncMock, MagicMock

from aiohttp import ClientResponseError
from pyaqvify import AqvifyAccount, AqvifyAuthException
import pytest

from homeassistant.components.aqvify.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_full_flow(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_aqvify_client: MagicMock
) -> None:
    """Test full flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_API_KEY: "test-api-key",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Aqvify"
    assert result["data"] == {
        CONF_API_KEY: "test-api-key",
    }
    assert result["result"].unique_id == "test_account_id"
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("side_effect", "error_base"),
    [
        (AqvifyAuthException, "invalid_auth"),
        (
            ClientResponseError(request_info=None, history=None, status=500),
            "cannot_connect",
        ),
        (TypeError, "unknown"),
    ],
)
async def test_form_invalid(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_aqvify_client: MagicMock,
    side_effect: Exception,
    error_base: str,
) -> None:
    """Test we handle errors during form submission."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    mock_aqvify_client.async_get_account_id.side_effect = side_effect
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_API_KEY: "test-api-key",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error_base}

    # Make sure the config flow tests finish with either an
    # FlowResultType.CREATE_ENTRY or FlowResultType.ABORT so
    # we can show the config flow is able to recover from an error.
    mock_aqvify_client.async_get_account_id.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_API_KEY: "test-api-key",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Aqvify"
    assert result["data"] == {
        CONF_API_KEY: "test-api-key",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_same_account_setup(
    hass: HomeAssistant, mock_config_entry: AsyncMock, mock_aqvify_client: MagicMock
) -> None:
    """Test setup same account twice."""

    # Create an existing config entry for the same user account
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_API_KEY: "test-api-key2",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("return_value", "expected_reason"),
    [
        ("test_account_id", "reauth_successful"),
        ("test_different_account_id", "unique_id_mismatch"),
    ],
    ids=["same_account", "different_account"],
)
async def test_reauth_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_aqvify_client: MagicMock,
    return_value: str,
    expected_reason: str,
) -> None:
    """Test reauthentication."""

    result = await mock_config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    mock_aqvify_client.async_get_account_id.return_value = AqvifyAccount(
        {"accountId": return_value}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_API_KEY: "test-api-key"}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == expected_reason


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (AqvifyAuthException, "invalid_auth"),
        (
            ClientResponseError(request_info=None, history=None, status=500),
            "cannot_connect",
        ),
    ],
    ids=["invalid_auth", "cannot_connect"],
)
async def test_reauth_flow_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_aqvify_client: MagicMock,
    side_effect: Exception,
    expected_error: str,
) -> None:
    """Test reauthentication error handling."""

    result = await mock_config_entry.start_reauth_flow(hass)

    mock_aqvify_client.async_get_account_id.side_effect = side_effect
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_API_KEY: "test-api-key"}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}

    # Make sure the config flow tests finish with FlowResultType.ABORT so
    # we can show the config flow is able to recover from an error.
    mock_aqvify_client.async_get_account_id.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_API_KEY: "test-api-key",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
