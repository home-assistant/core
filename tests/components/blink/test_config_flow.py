"""Test the Blink config flow."""

from unittest.mock import MagicMock, patch

from blinkpy.auth import BlinkTwoFARequiredError, LoginError, TokenRefreshFailed
from blinkpy.blinkpy import BlinkSetupError

from homeassistant import config_entries
from homeassistant.components.blink import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_form_2fa(hass: HomeAssistant) -> None:
    """Test we get the 2fa form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.blink.config_flow.Blink.start",
        side_effect=BlinkTwoFARequiredError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": "blink@example.com", "password": "example"},
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "2fa"

    with (
        patch("homeassistant.components.blink.config_flow.Blink.start"),
        patch(
            "homeassistant.components.blink.config_flow.Blink.send_2fa_code",
            return_value=True,
        ),
        patch(
            "homeassistant.components.blink.config_flow.Blink.setup_urls",
            return_value=True,
        ),
        patch(
            "homeassistant.components.blink.async_setup_entry", return_value=True
        ) as mock_setup_entry,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"], {"pin": "1234"}
        )
        await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["title"] == "blink"
    assert result3["result"].unique_id == "blink@example.com"
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_2fa_connect_error(hass: HomeAssistant) -> None:
    """Test we report a connect error during 2fa setup."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.blink.config_flow.Blink.start",
        side_effect=BlinkTwoFARequiredError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": "blink@example.com", "password": "example"},
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "2fa"

    with (
        patch("homeassistant.components.blink.config_flow.Blink.start"),
        patch(
            "homeassistant.components.blink.config_flow.Blink.send_2fa_code",
            side_effect=BlinkSetupError,
        ),
        patch(
            "homeassistant.components.blink.async_setup_entry",
            return_value=True,
        ),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"], {"pin": "1234"}
        )

    assert result3["type"] is FlowResultType.FORM
    assert result3["errors"] == {"base": "cannot_connect"}


async def test_form_2fa_invalid_key(hass: HomeAssistant) -> None:
    """Test we report an error if key is invalid."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.blink.config_flow.Blink.start",
        side_effect=BlinkTwoFARequiredError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": "blink@example.com", "password": "example"},
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "2fa"

    with (
        patch(
            "homeassistant.components.blink.config_flow.Blink.start",
        ),
        patch(
            "homeassistant.components.blink.config_flow.Blink.send_2fa_code",
            side_effect=TokenRefreshFailed,
        ),
        patch(
            "homeassistant.components.blink.async_setup_entry",
            return_value=True,
        ),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"], {"pin": "1234"}
        )

    assert result3["type"] is FlowResultType.FORM
    assert result3["errors"] == {"base": "invalid_access_token"}


async def test_form_2fa_unknown_error(hass: HomeAssistant) -> None:
    """Test we report an unknown error during 2fa setup."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.blink.config_flow.Blink.start",
        side_effect=BlinkTwoFARequiredError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": "blink@example.com", "password": "example"},
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "2fa"

    with (
        patch("homeassistant.components.blink.config_flow.Blink.start"),
        patch(
            "homeassistant.components.blink.config_flow.Blink.send_2fa_code",
            side_effect=Exception,
        ),
        patch(
            "homeassistant.components.blink.async_setup_entry",
            return_value=True,
        ),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"], {"pin": "1234"}
        )

    assert result3["type"] is FlowResultType.FORM
    assert result3["errors"] == {"base": "unknown"}


async def test_form_2fa_wrong_pin(hass: HomeAssistant) -> None:
    """Test we report invalid auth when send_2fa_code returns False."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.blink.config_flow.Blink.start",
        side_effect=BlinkTwoFARequiredError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": "blink@example.com", "password": "example"},
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "2fa"

    with (
        patch("homeassistant.components.blink.config_flow.Blink.start"),
        patch(
            "homeassistant.components.blink.config_flow.Blink.send_2fa_code",
            return_value=False,
        ),
        patch(
            "homeassistant.components.blink.async_setup_entry",
            return_value=True,
        ),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"], {"pin": "1234"}
        )

    assert result3["type"] is FlowResultType.FORM
    assert result3["errors"] == {"base": "invalid_auth"}


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.blink.config_flow.Blink.start",
        side_effect=LoginError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"username": "blink@example.com", "password": "example"}
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_start_returns_false(hass: HomeAssistant) -> None:
    """Test we handle auth failure when blink.start() returns False without raising.

    blink.start() catches LoginError/TokenRefreshFailed internally and returns
    False instead of re-raising, so validate_input must check the return value.
    """
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.blink.config_flow.Blink.start",
        return_value=False,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"username": "blink@example.com", "password": "example"}
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_unknown_error(hass: HomeAssistant) -> None:
    """Test we handle unknown error at startup."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.blink.config_flow.Blink.start",
        side_effect=KeyError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"username": "blink@example.com", "password": "example"}
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_reauth_shows_user_step(hass: HomeAssistant) -> None:
    """Test reauth shows the user form."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"username": "blink@example.com", "password": "invalid_password"},
    )
    mock_entry.add_to_hass(hass)
    result = await mock_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"


async def test_form_user_omits_hardware_id(hass: HomeAssistant) -> None:
    """Test initial setup omits hardware_id, letting blinkpy generate a UUID.

    Blink's OAuth endpoint rejects the old hardcoded "Home Assistant"
    literal; a fresh install has no prior hardware_id to reuse.
    """
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_auth = MagicMock()
    mock_auth.login_attributes = {
        "username": "blink@example.com",
        "password": "example",
        "hardware_id": "11111111-1111-1111-1111-111111111111",
    }

    with (
        patch(
            "homeassistant.components.blink.config_flow.Auth",
            return_value=mock_auth,
        ) as mock_auth_class,
        patch(
            "homeassistant.components.blink.config_flow.Blink.start",
            return_value=True,
        ),
        patch("homeassistant.components.blink.async_setup_entry", return_value=True),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": "blink@example.com", "password": "example"},
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    login_data = mock_auth_class.call_args[0][0]
    assert "hardware_id" not in login_data


async def test_reauth_reuses_existing_hardware_id(hass: HomeAssistant) -> None:
    """Test reauth passes along the previously stored, valid hardware_id."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "username": "blink@example.com",
            "password": "invalid_password",
            "hardware_id": "existing-valid-uuid",
        },
        version=5,
    )
    mock_entry.add_to_hass(hass)
    result = await mock_entry.start_reauth_flow(hass)

    mock_auth = MagicMock()
    mock_auth.login_attributes = {
        "username": "blink@example.com",
        "password": "new_password",
        "hardware_id": "existing-valid-uuid",
    }

    with (
        patch(
            "homeassistant.components.blink.config_flow.Auth",
            return_value=mock_auth,
        ) as mock_auth_class,
        patch(
            "homeassistant.components.blink.config_flow.Blink.start",
            return_value=True,
        ),
        patch("homeassistant.components.blink.async_setup_entry", return_value=True),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": "blink@example.com", "password": "new_password"},
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"
    login_data = mock_auth_class.call_args[0][0]
    assert login_data["hardware_id"] == "existing-valid-uuid"


async def test_reauth_does_not_reuse_legacy_hardware_id(hass: HomeAssistant) -> None:
    """Test reauth does not resend the rejected legacy hardware_id."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "username": "blink@example.com",
            "password": "invalid_password",
            "hardware_id": "Home Assistant",
        },
        version=4,
    )
    mock_entry.add_to_hass(hass)
    result = await mock_entry.start_reauth_flow(hass)

    mock_auth = MagicMock()
    mock_auth.login_attributes = {
        "username": "blink@example.com",
        "password": "new_password",
        "hardware_id": "22222222-2222-2222-2222-222222222222",
    }

    with (
        patch(
            "homeassistant.components.blink.config_flow.Auth",
            return_value=mock_auth,
        ) as mock_auth_class,
        patch(
            "homeassistant.components.blink.config_flow.Blink.start",
            return_value=True,
        ),
        patch("homeassistant.components.blink.async_setup_entry", return_value=True),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": "blink@example.com", "password": "new_password"},
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    login_data = mock_auth_class.call_args[0][0]
    assert "hardware_id" not in login_data


async def test_reconfigure_reuses_existing_hardware_id(hass: HomeAssistant) -> None:
    """Test reconfigure reuses the stored, valid hardware_id when re-submitting."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "username": "blink@example.com",
            "password": "old_password",
            "hardware_id": "existing-valid-uuid",
        },
        version=5,
    )
    mock_entry.add_to_hass(hass)
    result = await mock_entry.start_reconfigure_flow(hass)

    mock_auth = MagicMock()

    with (
        patch(
            "homeassistant.components.blink.config_flow.Auth",
            return_value=mock_auth,
        ) as mock_auth_class,
        patch(
            "homeassistant.components.blink.config_flow.Blink.start",
            return_value=False,
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": "blink@example.com", "password": "new_password"},
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}
    login_data = mock_auth_class.call_args[0][0]
    assert login_data["hardware_id"] == "existing-valid-uuid"
