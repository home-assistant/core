"""Tests for the LoJack config flow."""

from unittest.mock import AsyncMock, patch

from homeassistant.components.lojack.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import MockApiError, MockAuthenticationError
from .const import TEST_PASSWORD, TEST_USERNAME

from tests.common import MockConfigEntry


async def test_full_user_flow(
    hass: HomeAssistant,
    mock_lojack_client: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test the full user configuration flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"LoJack ({TEST_USERNAME})"
    assert result["data"] == {
        CONF_USERNAME: TEST_USERNAME,
        CONF_PASSWORD: TEST_PASSWORD,
    }
    assert result["result"].unique_id == TEST_USERNAME.lower()


async def test_user_flow_invalid_auth(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test handling of invalid authentication."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with (
        patch(
            "homeassistant.components.lojack.config_flow.LoJackClient.create",
            side_effect=MockAuthenticationError("Invalid credentials"),
        ),
        patch(
            "homeassistant.components.lojack.config_flow.AuthenticationError",
            MockAuthenticationError,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: TEST_USERNAME,
                CONF_PASSWORD: "wrongpassword",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "invalid_auth"}


async def test_user_flow_cannot_connect(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test handling of connection errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with (
        patch(
            "homeassistant.components.lojack.config_flow.LoJackClient.create",
            side_effect=MockApiError("Connection failed"),
        ),
        patch(
            "homeassistant.components.lojack.config_flow.ApiError",
            MockApiError,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: TEST_USERNAME,
                CONF_PASSWORD: TEST_PASSWORD,
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_flow_unknown_error(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test handling of unknown errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.lojack.config_flow.LoJackClient.create",
        side_effect=Exception("Unknown error"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: TEST_USERNAME,
                CONF_PASSWORD: TEST_PASSWORD,
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "unknown"}


async def test_user_flow_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that duplicate accounts are rejected."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lojack_client: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test the reauthentication flow."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PASSWORD: "newpassword"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


async def test_reauth_flow_invalid_auth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test reauthentication with invalid credentials."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with (
        patch(
            "homeassistant.components.lojack.config_flow.LoJackClient.create",
            side_effect=MockAuthenticationError("Invalid credentials"),
        ),
        patch(
            "homeassistant.components.lojack.config_flow.AuthenticationError",
            MockAuthenticationError,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_PASSWORD: "wrongpassword"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": "invalid_auth"}


async def test_reauth_flow_cannot_connect(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test reauthentication with connection error."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with (
        patch(
            "homeassistant.components.lojack.config_flow.LoJackClient.create",
            side_effect=MockApiError("Connection failed"),
        ),
        patch(
            "homeassistant.components.lojack.config_flow.ApiError",
            MockApiError,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_PASSWORD: TEST_PASSWORD},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_flow_recovery_after_error(
    hass: HomeAssistant,
    mock_lojack_client: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test that user can recover after an error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    # First attempt fails
    with (
        patch(
            "homeassistant.components.lojack.config_flow.LoJackClient.create",
            side_effect=MockAuthenticationError("Invalid credentials"),
        ),
        patch(
            "homeassistant.components.lojack.config_flow.AuthenticationError",
            MockAuthenticationError,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: TEST_USERNAME,
                CONF_PASSWORD: "wrongpassword",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    # Second attempt succeeds
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_reconfigure_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lojack_client: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test the reconfigure flow."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: "newpassword",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"


async def test_reconfigure_flow_invalid_auth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test reconfigure with invalid credentials."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    with (
        patch(
            "homeassistant.components.lojack.config_flow.LoJackClient.create",
            side_effect=MockAuthenticationError("Invalid credentials"),
        ),
        patch(
            "homeassistant.components.lojack.config_flow.AuthenticationError",
            MockAuthenticationError,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: TEST_USERNAME,
                CONF_PASSWORD: "wrongpassword",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {"base": "invalid_auth"}


async def test_reconfigure_flow_cannot_connect(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test reconfigure with connection error."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    with (
        patch(
            "homeassistant.components.lojack.config_flow.LoJackClient.create",
            side_effect=MockApiError("Connection failed"),
        ),
        patch(
            "homeassistant.components.lojack.config_flow.ApiError",
            MockApiError,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: TEST_USERNAME,
                CONF_PASSWORD: TEST_PASSWORD,
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_reconfigure_flow_account_mismatch(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lojack_client: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test reconfigure with different username."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    # Try to change to a different username
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "different@example.com",
            CONF_PASSWORD: TEST_PASSWORD,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "account_mismatch"
