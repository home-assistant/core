"""Tests for the Glutz eAccess config flow."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

from pyglutz_eaccess import GlutzAuthError, GlutzConnectionError
import pytest

from homeassistant.components.glutz_eaccess.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import setup_integration

from tests.common import MockConfigEntry

VALID_CREDENTIALS = {
    CONF_HOST: "https://example.com",
    CONF_USERNAME: "user@example.com",
    CONF_PASSWORD: "secret",
}


# ---------------------------------------------------------------------------
# User step: shows menu
# ---------------------------------------------------------------------------


async def test_user_step_shows_menu(hass: HomeAssistant) -> None:
    """Test the user step returns a menu."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    assert result["type"] is FlowResultType.MENU
    assert "credentials" in result["menu_options"]
    assert "invitation" in result["menu_options"]


# ---------------------------------------------------------------------------
# Credentials step
# ---------------------------------------------------------------------------


async def test_credentials_step_shows_form(hass: HomeAssistant) -> None:
    """Test the credentials step shows a form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "credentials"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "credentials"
    assert not result["errors"]


async def test_credentials_success_creates_entry(
    hass: HomeAssistant,
    mock_glutz_client: AsyncMock,
) -> None:
    """Test successful credentials login creates a config entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "credentials"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=VALID_CREDENTIALS
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Building"
    assert result["data"] == VALID_CREDENTIALS


async def test_credentials_success_uses_default_title_when_no_name(
    hass: HomeAssistant,
    mock_glutz_client: AsyncMock,
) -> None:
    """Test that entry title falls back to DEFAULT_TITLE when system has no name."""
    mock_glutz_client.get_system_info.return_value = {"id": "SYS1"}

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "credentials"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=VALID_CREDENTIALS
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Glutz eAccess"


async def test_credentials_aborts_if_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_glutz_client: AsyncMock,
) -> None:
    """Test abort when a unique_id already exists."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "credentials"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=VALID_CREDENTIALS
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_credentials_no_system_id_returns_error(
    hass: HomeAssistant,
    mock_glutz_client: AsyncMock,
) -> None:
    """Test cannot_connect error when system info returns no ID."""
    mock_glutz_client.get_system_info.return_value = {}

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "credentials"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=VALID_CREDENTIALS
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (GlutzAuthError, "invalid_auth"),
        (GlutzConnectionError, "cannot_connect"),
    ],
)
async def test_credentials_api_error_returns_form_error(
    hass: HomeAssistant,
    mock_glutz_client: AsyncMock,
    side_effect: type[Exception],
    expected_error: str,
) -> None:
    """Test that API errors map to the expected form error key."""
    mock_glutz_client.get_access_points.side_effect = side_effect

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "credentials"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=VALID_CREDENTIALS
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}


# ---------------------------------------------------------------------------
# Invitation step
# ---------------------------------------------------------------------------


async def test_invitation_step_shows_form(hass: HomeAssistant) -> None:
    """Test the invitation step shows a form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "invitation"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "invitation"


async def test_invitation_invalid_url_returns_error(hass: HomeAssistant) -> None:
    """Test invalid invitation URL returns error."""
    with patch(
        "homeassistant.components.glutz_eaccess.config_flow.parse_invitation",
        side_effect=ValueError("bad url"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "invitation"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"invite_url": "not-a-valid-url"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_invitation"}


async def test_invitation_resolve_connection_error(hass: HomeAssistant) -> None:
    """Test connection error during host resolution."""
    with (
        patch(
            "homeassistant.components.glutz_eaccess.config_flow.parse_invitation",
            return_value={
                "cloud_host": "cloud.example.com",
                "system_path": "/sys/1",
                "email": "u@example.com",
                "token": "tok",
            },
        ),
        patch(
            "homeassistant.components.glutz_eaccess.config_flow.resolve_instance_host",
            side_effect=GlutzConnectionError,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "invitation"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"invite_url": "https://invite.example.com"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_invitation_confirm_invalid_password(hass: HomeAssistant) -> None:
    """Test that a weak password returns invalid_password error."""
    with (
        patch(
            "homeassistant.components.glutz_eaccess.config_flow.parse_invitation",
            return_value={
                "cloud_host": "cloud.example.com",
                "system_path": "/sys/1",
                "email": "u@example.com",
                "token": "tok",
            },
        ),
        patch(
            "homeassistant.components.glutz_eaccess.config_flow.resolve_instance_host",
            return_value="instance.example.com",
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "invitation"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"invite_url": "https://invite.example.com"}
        )

    # Now on invitation_confirm step — submit weak password
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "https://instance.example.com",
            CONF_USERNAME: "u@example.com",
            CONF_PASSWORD: "weakpass",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_password"}


async def test_invitation_confirm_creates_entry(
    hass: HomeAssistant,
    mock_glutz_client: AsyncMock,
) -> None:
    """Test successful invitation confirm creates a config entry."""
    with (
        patch(
            "homeassistant.components.glutz_eaccess.config_flow.parse_invitation",
            return_value={
                "cloud_host": "cloud.example.com",
                "system_path": "/sys/1",
                "email": "u@example.com",
                "token": "tok",
                "system_id": "SYS1",
            },
        ),
        patch(
            "homeassistant.components.glutz_eaccess.config_flow.resolve_instance_host",
            return_value="instance.example.com",
        ),
        patch(
            "homeassistant.components.glutz_eaccess.config_flow.set_new_password",
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "invitation"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"invite_url": "https://invite.example.com"}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "https://instance.example.com",
                CONF_USERNAME: "u@example.com",
                CONF_PASSWORD: "ValidP4ss!",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


# ---------------------------------------------------------------------------
# Reauth step
# ---------------------------------------------------------------------------


async def test_reauth_confirm_shows_form(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_glutz_client: AsyncMock,
) -> None:
    """Test reauth confirm step shows a form."""
    await setup_integration(hass, mock_config_entry)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"


async def test_reauth_confirm_success_updates_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_glutz_client: AsyncMock,
) -> None:
    """Test successful reauth confirm updates entry and reloads."""
    await setup_integration(hass, mock_config_entry)

    result = await mock_config_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "https://example.com",
            CONF_USERNAME: "user@example.com",
            CONF_PASSWORD: "newpassword",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_PASSWORD] == "newpassword"


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (GlutzAuthError, "invalid_auth"),
        (GlutzConnectionError, "cannot_connect"),
    ],
)
async def test_reauth_confirm_api_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_glutz_client: AsyncMock,
    side_effect: type[Exception],
    expected_error: str,
) -> None:
    """Test that API errors in reauth confirm map to form errors."""
    await setup_integration(hass, mock_config_entry)

    mock_glutz_client.get_access_points.side_effect = side_effect

    result = await mock_config_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "https://example.com",
            CONF_USERNAME: "user@example.com",
            CONF_PASSWORD: "newpassword",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}


# ---------------------------------------------------------------------------
# Reconfigure step
# ---------------------------------------------------------------------------


async def test_reconfigure_shows_form(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_glutz_client: AsyncMock,
) -> None:
    """Test reconfigure step shows a form."""
    await setup_integration(hass, mock_config_entry)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"


async def test_reconfigure_success_updates_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_glutz_client: AsyncMock,
) -> None:
    """Test successful reconfigure updates entry and reloads."""
    await setup_integration(hass, mock_config_entry)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "https://new.example.com",
            CONF_USERNAME: "new@example.com",
            CONF_PASSWORD: "newpassword",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_HOST] == "https://new.example.com"


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (GlutzAuthError, "invalid_auth"),
        (GlutzConnectionError, "cannot_connect"),
    ],
)
async def test_reconfigure_api_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_glutz_client: AsyncMock,
    side_effect: type[Exception],
    expected_error: str,
) -> None:
    """Test that API errors in reconfigure map to form errors."""
    await setup_integration(hass, mock_config_entry)

    mock_glutz_client.get_access_points.side_effect = side_effect

    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "https://example.com",
            CONF_USERNAME: "user@example.com",
            CONF_PASSWORD: "newpassword",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}


async def test_reconfigure_no_system_id_returns_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_glutz_client: AsyncMock,
) -> None:
    """Test cannot_connect error in reconfigure when system info has no ID."""
    await setup_integration(hass, mock_config_entry)

    mock_glutz_client.get_system_info.return_value = {}

    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "https://example.com",
            CONF_USERNAME: "user@example.com",
            CONF_PASSWORD: "newpassword",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_reconfigure_wrong_account_aborts(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_glutz_client: AsyncMock,
) -> None:
    """Test that reconfigure aborts when system ID doesn't match the entry."""
    await setup_integration(hass, mock_config_entry)

    mock_glutz_client.get_system_info.return_value = {"id": "DIFFERENT_ID", "name": "Other"}

    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "https://example.com",
            CONF_USERNAME: "user@example.com",
            CONF_PASSWORD: "newpassword",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_account"


async def test_reauth_no_system_id_returns_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_glutz_client: AsyncMock,
) -> None:
    """Test cannot_connect error in reauth confirm when system info has no ID."""
    await setup_integration(hass, mock_config_entry)

    mock_glutz_client.get_system_info.return_value = {}

    result = await mock_config_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "https://example.com",
            CONF_USERNAME: "user@example.com",
            CONF_PASSWORD: "newpassword",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_reauth_wrong_account_aborts(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_glutz_client: AsyncMock,
) -> None:
    """Test that reauth aborts when system ID doesn't match the entry."""
    await setup_integration(hass, mock_config_entry)

    mock_glutz_client.get_system_info.return_value = {"id": "DIFFERENT_ID", "name": "Other"}

    result = await mock_config_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "https://example.com",
            CONF_USERNAME: "user@example.com",
            CONF_PASSWORD: "newpassword",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_account"
