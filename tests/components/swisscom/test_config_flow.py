"""Tests for the Swisscom Internet-Box config flow."""

from unittest.mock import MagicMock

import pytest
from pytest_homeassistant.common import MockConfigEntry
from swisscom_internet_box import SwisscomAuthError, SwisscomConnectionError

from homeassistant.components.swisscom.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import TEST_FORMATTED_MAC, TEST_MODEL_NAME, USER_INPUT

NEW_PASSWORD = "new-password"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_success(
    hass: HomeAssistant, mock_swisscom_client: MagicMock
) -> None:
    """Test a successful user-initiated config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_MODEL_NAME
    assert result["data"] == USER_INPUT
    assert result["result"].unique_id == TEST_FORMATTED_MAC


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (SwisscomAuthError("bad creds"), "invalid_auth"),
        (SwisscomConnectionError("unreachable"), "cannot_connect"),
        (RuntimeError("boom"), "unknown"),
    ],
    ids=["invalid_auth", "cannot_connect", "unknown"],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_error_and_recovery(
    hass: HomeAssistant,
    mock_swisscom_client: MagicMock,
    side_effect: Exception,
    expected_error: str,
) -> None:
    """Test user flow shows the correct error and the user can retry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    mock_swisscom_client.login.side_effect = side_effect
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=USER_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}

    mock_swisscom_client.login.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_MODEL_NAME
    assert result["data"] == USER_INPUT
    assert result["result"].unique_id == TEST_FORMATTED_MAC


async def test_user_flow_duplicate(
    hass: HomeAssistant,
    mock_swisscom_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that duplicate boxes are rejected."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=USER_INPUT
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_no_model_name_uses_default_title(
    hass: HomeAssistant, mock_swisscom_client: MagicMock
) -> None:
    """Test the entry falls back to a default title when the box reports no model."""
    mock_swisscom_client.get_box_info.return_value.model_name = ""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Internet-Box"
    assert result["result"].unique_id == TEST_FORMATTED_MAC


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reauth_flow(
    hass: HomeAssistant,
    mock_swisscom_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a successful reauthentication flow."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_PASSWORD: NEW_PASSWORD}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data == {**USER_INPUT, CONF_PASSWORD: NEW_PASSWORD}


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        pytest.param(SwisscomAuthError, "invalid_auth", id="invalid_auth"),
        pytest.param(SwisscomConnectionError, "cannot_connect", id="cannot_connect"),
        pytest.param(RuntimeError, "unknown", id="unknown"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_reauth_flow_error_and_recovery(
    hass: HomeAssistant,
    mock_swisscom_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    side_effect: type[Exception],
    expected_error: str,
) -> None:
    """Test reauthentication shows the correct error and the user can retry."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)

    mock_swisscom_client.login.side_effect = side_effect
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_PASSWORD: NEW_PASSWORD}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": expected_error}

    mock_swisscom_client.login.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_PASSWORD: NEW_PASSWORD}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data == {**USER_INPUT, CONF_PASSWORD: NEW_PASSWORD}


async def test_reauth_flow_unique_id_mismatch(
    hass: HomeAssistant,
    mock_swisscom_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reauthentication aborts when a different box answers."""
    mock_config_entry.add_to_hass(hass)
    mock_swisscom_client.get_box_info.return_value.base_mac = "11:22:33:44:55:66"

    result = await mock_config_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_PASSWORD: NEW_PASSWORD}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"
    assert mock_config_entry.data == USER_INPUT
