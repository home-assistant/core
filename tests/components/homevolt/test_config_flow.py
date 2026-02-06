"""Tests for the Homevolt config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from homevolt import HomevoltAuthenticationError, HomevoltConnectionError
import pytest

from homeassistant.components.homevolt.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_full_flow_success(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_homevolt_client: MagicMock
) -> None:
    """Test a complete successful user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    user_input = {
        CONF_HOST: "192.168.1.100",
        CONF_PASSWORD: "test-password",
    }

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Homevolt"
    assert result["data"] == user_input
    assert result["result"].unique_id == "40580137858664"
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("exception", "expected_error"),
    [
        (HomevoltAuthenticationError, "invalid_auth"),
        (HomevoltConnectionError, "cannot_connect"),
        (Exception, "unknown"),
    ],
)
async def test_step_user_errors(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_homevolt_client: MagicMock,
    exception: Exception,
    expected_error: str,
) -> None:
    """Test error cases for the user step with recovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    user_input = {
        CONF_HOST: "192.168.1.100",
        CONF_PASSWORD: "test-password",
    }

    mock_homevolt_client.update_info.side_effect = exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": expected_error}

    mock_homevolt_client.update_info.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Homevolt"
    assert result["data"] == user_input
    assert result["result"].unique_id == "40580137858664"
    assert len(mock_setup_entry.mock_calls) == 1


async def test_duplicate_entry(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_homevolt_client: MagicMock,
) -> None:
    """Test that a duplicate device_id aborts the flow."""
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.168.1.100", CONF_PASSWORD: "test-password"},
        unique_id="40580137858664",
    )
    existing_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    user_input = {
        CONF_HOST: "192.168.1.200",
        CONF_PASSWORD: "test-password",
    }

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
