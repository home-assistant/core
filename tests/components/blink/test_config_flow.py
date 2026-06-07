"""Test the Blink config flow."""

from unittest.mock import patch

import pytest

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


@pytest.mark.parametrize(
    ("side_effect", "error_key"),
    [
        pytest.param(BlinkSetupError, "cannot_connect", id="connect_error"),
        pytest.param(TokenRefreshFailed, "invalid_access_token", id="invalid_key"),
        pytest.param(Exception, "unknown", id="unknown_error"),
    ],
)
async def test_form_2fa_error(
    hass: HomeAssistant, side_effect: type[Exception], error_key: str
) -> None:
    """Test we report errors during 2fa setup."""
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
            side_effect=side_effect,
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
    assert result3["errors"] == {"base": error_key}


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
    assert result["step_id"] == "reauth_confirm"


async def test_reauth_completes(hass: HomeAssistant) -> None:
    """Test successful reauth updates the entry and reloads."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"username": "blink@example.com", "password": "invalid_password"},
    )
    mock_entry.add_to_hass(hass)
    result = await mock_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with (
        patch(
            "homeassistant.components.blink.config_flow.Blink.start",
            return_value=True,
        ),
        patch(
            "homeassistant.components.blink.async_setup_entry", return_value=True
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": "blink@example.com", "password": "new_password"},
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"


async def test_form_user(hass: HomeAssistant) -> None:
    """Test successful setup without 2FA."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with (
        patch(
            "homeassistant.components.blink.config_flow.Blink.start",
            return_value=True,
        ),
        patch(
            "homeassistant.components.blink.async_setup_entry", return_value=True
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": "blink@example.com", "password": "example"},
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "blink"
    assert result2["result"].unique_id == "blink@example.com"
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_start_failed(hass: HomeAssistant) -> None:
    """Test we handle when blink.start() returns False without raising."""
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


async def test_form_2fa_send_failed(hass: HomeAssistant) -> None:
    """Test we handle when send_2fa_code returns False."""
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

    with patch(
        "homeassistant.components.blink.config_flow.Blink.send_2fa_code",
        return_value=False,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"], {"pin": "1234"}
        )

    assert result3["type"] is FlowResultType.FORM
    assert result3["errors"] == {"base": "cannot_connect"}


async def test_reconfigure_shows_form(hass: HomeAssistant) -> None:
    """Test reconfigure shows the reconfigure form."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"username": "blink@example.com", "password": "old_password"},
    )
    mock_entry.add_to_hass(hass)
    result = await mock_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"


async def test_reconfigure_completes(hass: HomeAssistant) -> None:
    """Test successful reconfiguration updates the entry and reloads."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"username": "blink@example.com", "password": "old_password"},
    )
    mock_entry.add_to_hass(hass)
    result = await mock_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    with (
        patch(
            "homeassistant.components.blink.config_flow.Blink.start",
            return_value=True,
        ),
        patch(
            "homeassistant.components.blink.async_setup_entry", return_value=True
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": "blink@example.com", "password": "new_password"},
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reconfigure_successful"
