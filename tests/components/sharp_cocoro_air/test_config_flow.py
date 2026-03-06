"""Test the Sharp COCORO Air config flow."""

from unittest.mock import AsyncMock

from aiosharp_cocoro_air import SharpAuthError, SharpConnectionError
import pytest

from homeassistant.components.sharp_cocoro_air.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import CONFIG_INPUT

from tests.common import MockConfigEntry


async def test_user_flow_success(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_sharp_config_flow: AsyncMock,
) -> None:
    """Test successful user config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=CONFIG_INPUT,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Sharp COCORO Air (test@example.com)"
    assert result["data"] == CONFIG_INPUT
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (SharpAuthError(), "invalid_auth"),
        (SharpConnectionError(), "cannot_connect"),
        (Exception(), "unknown"),
    ],
)
async def test_user_flow_errors(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_sharp_config_flow: AsyncMock,
    side_effect: Exception,
    expected_error: str,
) -> None:
    """Test user flow handles errors and allows retry."""
    mock_sharp_config_flow.authenticate.side_effect = side_effect

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=CONFIG_INPUT,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == expected_error

    # Recover
    mock_sharp_config_flow.authenticate.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=CONFIG_INPUT,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_already_configured(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_sharp_config_flow: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test aborting if account is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=CONFIG_INPUT,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth_flow_success(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_sharp_config_flow: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test successful reauthentication flow."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=CONFIG_INPUT,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


async def test_reconfigure_flow_success(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_sharp_config_flow: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test successful reconfiguration flow."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=CONFIG_INPUT,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (SharpAuthError(), "invalid_auth"),
        (SharpConnectionError(), "cannot_connect"),
        (Exception(), "unknown"),
    ],
)
async def test_reconfigure_flow_errors(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_sharp_config_flow: AsyncMock,
    mock_config_entry: MockConfigEntry,
    side_effect: Exception,
    expected_error: str,
) -> None:
    """Test reconfigure flow handles errors and allows retry."""
    mock_config_entry.add_to_hass(hass)
    mock_sharp_config_flow.authenticate.side_effect = side_effect

    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=CONFIG_INPUT,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == expected_error

    # Recover
    mock_sharp_config_flow.authenticate.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=CONFIG_INPUT,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"


async def test_reauth_flow_unique_id_mismatch(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_sharp_config_flow: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reauth flow aborts when email doesn't match original account."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            "email": "different@example.com",
            "password": "test-password",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (SharpAuthError(), "invalid_auth"),
        (SharpConnectionError(), "cannot_connect"),
        (Exception(), "unknown"),
    ],
)
async def test_reauth_flow_errors(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_sharp_config_flow: AsyncMock,
    mock_config_entry: MockConfigEntry,
    side_effect: Exception,
    expected_error: str,
) -> None:
    """Test reauth flow handles errors and allows retry."""
    mock_config_entry.add_to_hass(hass)
    mock_sharp_config_flow.authenticate.side_effect = side_effect

    result = await mock_config_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=CONFIG_INPUT,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == expected_error

    # Recover
    mock_sharp_config_flow.authenticate.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=CONFIG_INPUT,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
