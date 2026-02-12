"""Test the Hypontech Cloud config flow."""

from unittest.mock import AsyncMock, patch

from hyponcloud import AuthenticationError
import pytest

from homeassistant.components.hypontech.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

TEST_USER_INPUT = {
    CONF_USERNAME: "test@example.com",
    CONF_PASSWORD: "test-password",
}


async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with (
        patch(
            "homeassistant.components.hypontech.config_flow.HyponCloud.connect",
        ),
        patch(
            "homeassistant.components.hypontech.config_flow.HyponCloud.get_admin_info",
        ) as mock_get_admin_info,
    ):
        mock_admin_info = AsyncMock()
        mock_admin_info.id = "mock_account_id_123"
        mock_get_admin_info.return_value = mock_admin_info
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_USER_INPUT,
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "test@example.com"
    assert result["data"] == TEST_USER_INPUT
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("side_effect", "error_message"),
    [
        (AuthenticationError, "invalid_auth"),
        (ConnectionError, "cannot_connect"),
        (TimeoutError, "cannot_connect"),
    ],
)
async def test_form_errors(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    side_effect: Exception,
    error_message: str,
) -> None:
    """Test we handle errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "homeassistant.components.hypontech.config_flow.HyponCloud.connect",
        side_effect=side_effect,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_USER_INPUT,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error_message}

    # Make sure the config flow tests finish with either an
    # FlowResultType.CREATE_ENTRY or FlowResultType.ABORT so
    # we can show the config flow is able to recover from an error.
    with (
        patch(
            "homeassistant.components.hypontech.config_flow.HyponCloud.connect",
        ),
        patch(
            "homeassistant.components.hypontech.config_flow.HyponCloud.get_admin_info",
        ) as mock_get_admin_info,
    ):
        mock_admin_info = AsyncMock()
        mock_admin_info.id = "mock_account_id_123"
        mock_get_admin_info.return_value = mock_admin_info
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_USER_INPUT,
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "test@example.com"
    assert result["data"] == TEST_USER_INPUT
    assert len(mock_setup_entry.mock_calls) == 1


async def test_duplicate_entry(
    hass: HomeAssistant,
    create_entry,
) -> None:
    """Test that duplicate entries are prevented based on account ID."""
    # Create an existing entry with account ID
    create_entry()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with (
        patch(
            "homeassistant.components.hypontech.config_flow.HyponCloud.connect",
        ),
        patch(
            "homeassistant.components.hypontech.config_flow.HyponCloud.get_admin_info",
        ) as mock_get_admin_info,
    ):
        # Try to add the same account again.
        mock_admin_info = AsyncMock()
        mock_admin_info.id = "mock_account_id_123"
        mock_get_admin_info.return_value = mock_admin_info
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            TEST_USER_INPUT,
        )

    # Should abort because entry already exists
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth_flow(hass: HomeAssistant, create_entry) -> None:
    """Test reauthentication flow."""
    # Create an existing entry
    entry = create_entry(password="old-password")

    # Start reauth flow
    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    # Submit new credentials
    with (
        patch(
            "homeassistant.components.hypontech.config_flow.HyponCloud.connect",
        ),
        patch(
            "homeassistant.components.hypontech.config_flow.HyponCloud.get_admin_info",
        ) as mock_get_admin_info,
    ):
        mock_admin_info = AsyncMock()
        mock_admin_info.id = "mock_account_id_123"
        mock_get_admin_info.return_value = mock_admin_info
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {**TEST_USER_INPUT, CONF_PASSWORD: "new-password"},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_PASSWORD] == "new-password"


@pytest.mark.parametrize(
    ("side_effect", "error_message"),
    [
        (AuthenticationError, "invalid_auth"),
        (ConnectionError, "cannot_connect"),
        (TimeoutError, "cannot_connect"),
    ],
)
async def test_reauth_flow_errors(
    hass: HomeAssistant,
    create_entry,
    side_effect: Exception,
    error_message: str,
) -> None:
    """Test reauthentication flow with errors."""
    # Create an existing entry
    entry = create_entry(password="old-password")

    # Start reauth flow
    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    # Submit new credentials with error
    with patch(
        "homeassistant.components.hypontech.config_flow.HyponCloud.connect",
        side_effect=side_effect,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {**TEST_USER_INPUT, CONF_PASSWORD: "new-password"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error_message}

    # Verify flow can recover from error
    with (
        patch(
            "homeassistant.components.hypontech.config_flow.HyponCloud.connect",
        ),
        patch(
            "homeassistant.components.hypontech.config_flow.HyponCloud.get_admin_info",
        ) as mock_get_admin_info,
    ):
        mock_admin_info = AsyncMock()
        mock_admin_info.id = "mock_account_id_123"
        mock_get_admin_info.return_value = mock_admin_info
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {**TEST_USER_INPUT, CONF_PASSWORD: "new-password"},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


async def test_reauth_flow_wrong_account(hass: HomeAssistant, create_entry) -> None:
    """Test reauthentication flow with wrong account."""
    # Create an existing entry
    entry = create_entry()

    # Start reauth flow
    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    # Submit credentials for a different account
    with (
        patch(
            "homeassistant.components.hypontech.config_flow.HyponCloud.connect",
        ),
        patch(
            "homeassistant.components.hypontech.config_flow.HyponCloud.get_admin_info",
        ) as mock_get_admin_info,
    ):
        mock_admin_info = AsyncMock()
        mock_admin_info.id = "different_account_id_456"
        mock_get_admin_info.return_value = mock_admin_info
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {**TEST_USER_INPUT, CONF_USERNAME: "different@example.com"},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_account"
