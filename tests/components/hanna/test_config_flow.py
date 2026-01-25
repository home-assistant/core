"""Tests for the Hanna Instruments integration config flow."""

from unittest.mock import AsyncMock, MagicMock

from hanna_cloud import AuthenticationError
import pytest
from requests.exceptions import ConnectionError as RequestsConnectionError, Timeout

from homeassistant.components.hanna.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_full_flow(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_hanna_client: MagicMock,
) -> None:
    """Test full flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMAIL: "test@example.com",
            CONF_PASSWORD: "test-password",
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "test@example.com"
    assert result["data"] == {
        CONF_EMAIL: "test@example.com",
        CONF_PASSWORD: "test-password",
    }
    assert result["result"].unique_id == "test@example.com"


@pytest.mark.parametrize(
    ("exception", "expected_error"),
    [
        (
            AuthenticationError("Authentication failed"),
            "invalid_auth",
        ),
        (
            Timeout("Connection timeout"),
            "cannot_connect",
        ),
        (
            RequestsConnectionError("Connection failed"),
            "cannot_connect",
        ),
    ],
)
async def test_error_scenarios(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_hanna_client: MagicMock,
    exception: Exception,
    expected_error: str,
) -> None:
    """Test various error scenarios in the config flow."""
    mock_hanna_client.authenticate.side_effect = exception

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_EMAIL: "test@example.com", CONF_PASSWORD: "test-password"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": expected_error}

    # Repatch to succeed and complete the flow
    mock_hanna_client.authenticate.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_EMAIL: "test@example.com", CONF_PASSWORD: "test-password"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "test@example.com"
    assert result["data"] == {
        CONF_EMAIL: "test@example.com",
        CONF_PASSWORD: "test-password",
    }


async def test_duplicate_entry(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_hanna_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that duplicate entries are aborted."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_EMAIL: "test@example.com", CONF_PASSWORD: "test-password"},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
