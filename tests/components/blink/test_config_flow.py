"""Test the Blink config flow."""

from unittest.mock import patch

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
    assert result["step_id"] == "user"
