"""Tests for the Leviton Decora Wi-Fi config flow."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.decora_wifi.const import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import TEST_USER_ID, TEST_USERNAME, USER_INPUT

from tests.common import MockConfigEntry


async def test_user_flow_success(
    hass: HomeAssistant,
    mock_decora_wifi: MagicMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test a successful user-initiated config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_USERNAME
    assert result["data"] == USER_INPUT
    assert result["result"].unique_id == TEST_USER_ID


@pytest.mark.parametrize(
    ("login_return_value", "login_side_effect", "expected_error"),
    [
        (None, None, "invalid_auth"),
        (True, ValueError("Cannot connect"), "cannot_connect"),
    ],
)
async def test_user_flow_error_and_recovery(
    hass: HomeAssistant,
    mock_decora_wifi: MagicMock,
    mock_setup_entry: AsyncMock,
    login_return_value: bool | None,
    login_side_effect: Exception | None,
    expected_error: str,
) -> None:
    """Test user flow shows the correct error and that the user can retry successfully."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    # First attempt: error
    mock_decora_wifi.login.return_value = login_return_value
    mock_decora_wifi.login.side_effect = login_side_effect
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=USER_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}

    # Second attempt: success
    mock_decora_wifi.login.side_effect = None
    mock_decora_wifi.login.return_value = True
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_duplicate(
    hass: HomeAssistant,
    mock_decora_wifi: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that duplicate accounts are rejected."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=USER_INPUT
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_import_flow_success(
    hass: HomeAssistant,
    mock_decora_wifi: MagicMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test a successful YAML import flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=USER_INPUT,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_USERNAME
    assert result["data"] == USER_INPUT
    assert result["result"].unique_id == TEST_USER_ID


async def test_import_flow_invalid_auth(
    hass: HomeAssistant,
    mock_decora_wifi: MagicMock,
) -> None:
    """Test YAML import aborts on invalid auth."""
    mock_decora_wifi.login.return_value = None

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=USER_INPUT,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "invalid_auth"


async def test_import_flow_cannot_connect(
    hass: HomeAssistant,
    mock_decora_wifi: MagicMock,
) -> None:
    """Test YAML import aborts when connection fails."""
    mock_decora_wifi.login.side_effect = ValueError("Cannot connect")

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=USER_INPUT,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_import_flow_duplicate(
    hass: HomeAssistant,
    mock_decora_wifi: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test YAML import aborts when username already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=USER_INPUT,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
