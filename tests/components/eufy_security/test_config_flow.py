"""Test the Eufy Security config flow."""

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant import config_entries
from homeassistant.components.eufy_security.const import DOMAIN
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


class MockInvalidCredentialsError(Exception):
    """Mock InvalidCredentialsError for testing."""


class MockCannotConnectError(Exception):
    """Mock CannotConnectError for testing."""


class MockEufySecurityError(Exception):
    """Mock EufySecurityError for testing."""


async def test_form(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_eufy_api: MagicMock,
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMAIL: "test@example.com",
            CONF_PASSWORD: "test-password",
        },
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "test@example.com"
    assert result2["data"] == {
        CONF_EMAIL: "test@example.com",
        CONF_PASSWORD: "test-password",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with (
        patch(
            "homeassistant.components.eufy_security.config_flow.async_login",
            side_effect=MockInvalidCredentialsError,
        ),
        patch(
            "homeassistant.components.eufy_security.config_flow.InvalidCredentialsError",
            MockInvalidCredentialsError,
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_EMAIL: "test@example.com",
                CONF_PASSWORD: "wrong-password",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_connect(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with (
        patch(
            "homeassistant.components.eufy_security.config_flow.async_login",
            side_effect=MockCannotConnectError,
        ),
        patch(
            "homeassistant.components.eufy_security.config_flow.CannotConnectError",
            MockCannotConnectError,
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_EMAIL: "test@example.com",
                CONF_PASSWORD: "test-password",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_unknown_error(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test we handle unknown errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.eufy_security.config_flow.async_login",
        side_effect=RuntimeError("Unexpected error"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_EMAIL: "test@example.com",
                CONF_PASSWORD: "test-password",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_form_already_configured(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_eufy_api: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test we abort when account is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMAIL: "test@example.com",
            CONF_PASSWORD: "test-password",
        },
    )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


async def test_reauth_flow(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_eufy_api: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test reauthentication flow."""
    init_integration.async_start_reauth(hass)
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    [result] = flows
    assert result["step_id"] == "reauth_confirm"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_PASSWORD: "new-password",
        },
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"
    assert init_integration.data[CONF_PASSWORD] == "new-password"


async def test_reauth_flow_invalid_auth(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_eufy_api: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test reauthentication flow with invalid auth."""
    init_integration.async_start_reauth(hass)
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    [result] = flows

    with (
        patch(
            "homeassistant.components.eufy_security.config_flow.async_login",
            side_effect=MockInvalidCredentialsError,
        ),
        patch(
            "homeassistant.components.eufy_security.config_flow.InvalidCredentialsError",
            MockInvalidCredentialsError,
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_PASSWORD: "wrong-password",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}
