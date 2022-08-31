"""Test the Blink config flow."""
from unittest.mock import Mock, patch

from blinkpy.auth import LoginError
from blinkpy.blinkpy import BlinkSetupError

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.blink import DOMAIN

from tests.common import MockConfigEntry


async def test_form(hass):
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch("homeassistant.components.blink.config_flow.Auth.startup"), patch(
        "homeassistant.components.blink.config_flow.Auth.check_key_required",
        return_value=False,
    ), patch(
        "homeassistant.components.blink.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": "blink@example.com", "password": "example"},
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "blink"
    assert result2["result"].unique_id == "blink@example.com"
    assert result2["data"] == {
        "username": "blink@example.com",
        "password": "example",
        "device_id": "Home Assistant",
        "token": None,
        "host": None,
        "account_id": None,
        "client_id": None,
        "region_id": None,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_2fa(hass):
    """Test we get the 2fa form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch("homeassistant.components.blink.config_flow.Auth.startup"), patch(
        "homeassistant.components.blink.config_flow.Auth.check_key_required",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": "blink@example.com", "password": "example"},
        )

    assert result2["type"] == "form"
    assert result2["step_id"] == "2fa"

    with patch("homeassistant.components.blink.config_flow.Auth.startup"), patch(
        "homeassistant.components.blink.config_flow.Auth.check_key_required",
        return_value=False,
    ), patch(
        "homeassistant.components.blink.config_flow.Auth.send_auth_key",
        return_value=True,
    ), patch(
        "homeassistant.components.blink.config_flow.Blink.setup_urls",
        return_value=True,
    ), patch(
        "homeassistant.components.blink.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"], {"pin": "1234"}
        )
        await hass.async_block_till_done()

    assert result3["type"] == "create_entry"
    assert result3["title"] == "blink"
    assert result3["result"].unique_id == "blink@example.com"
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_2fa_connect_error(hass):
    """Test we report a connect error during 2fa setup."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch("homeassistant.components.blink.config_flow.Auth.startup"), patch(
        "homeassistant.components.blink.config_flow.Auth.check_key_required",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": "blink@example.com", "password": "example"},
        )

    assert result2["type"] == "form"
    assert result2["step_id"] == "2fa"

    with patch("homeassistant.components.blink.config_flow.Auth.startup"), patch(
        "homeassistant.components.blink.config_flow.Auth.check_key_required",
        return_value=False,
    ), patch(
        "homeassistant.components.blink.config_flow.Auth.send_auth_key",
        return_value=True,
    ), patch(
        "homeassistant.components.blink.config_flow.Blink.setup_urls",
        side_effect=BlinkSetupError,
    ), patch(
        "homeassistant.components.blink.async_setup_entry", return_value=True
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"], {"pin": "1234"}
        )

    assert result3["type"] == "form"
    assert result3["errors"] == {"base": "cannot_connect"}


async def test_form_2fa_invalid_key(hass):
    """Test we report an error if key is invalid."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch("homeassistant.components.blink.config_flow.Auth.startup"), patch(
        "homeassistant.components.blink.config_flow.Auth.check_key_required",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": "blink@example.com", "password": "example"},
        )

    assert result2["type"] == "form"
    assert result2["step_id"] == "2fa"

    with patch("homeassistant.components.blink.config_flow.Auth.startup",), patch(
        "homeassistant.components.blink.config_flow.Auth.check_key_required",
        return_value=False,
    ), patch(
        "homeassistant.components.blink.config_flow.Auth.send_auth_key",
        return_value=False,
    ), patch(
        "homeassistant.components.blink.config_flow.Blink.setup_urls",
        return_value=True,
    ), patch(
        "homeassistant.components.blink.async_setup_entry", return_value=True
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"], {"pin": "1234"}
        )

    assert result3["type"] == "form"
    assert result3["errors"] == {"base": "invalid_access_token"}


async def test_form_2fa_unknown_error(hass):
    """Test we report an unknown error during 2fa setup."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch("homeassistant.components.blink.config_flow.Auth.startup"), patch(
        "homeassistant.components.blink.config_flow.Auth.check_key_required",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": "blink@example.com", "password": "example"},
        )

    assert result2["type"] == "form"
    assert result2["step_id"] == "2fa"

    with patch("homeassistant.components.blink.config_flow.Auth.startup"), patch(
        "homeassistant.components.blink.config_flow.Auth.check_key_required",
        return_value=False,
    ), patch(
        "homeassistant.components.blink.config_flow.Auth.send_auth_key",
        return_value=True,
    ), patch(
        "homeassistant.components.blink.config_flow.Blink.setup_urls",
        side_effect=KeyError,
    ), patch(
        "homeassistant.components.blink.async_setup_entry", return_value=True
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"], {"pin": "1234"}
        )

    assert result3["type"] == "form"
    assert result3["errors"] == {"base": "unknown"}


async def test_form_invalid_auth(hass):
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.blink.config_flow.Auth.startup",
        side_effect=LoginError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"username": "blink@example.com", "password": "example"}
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_unknown_error(hass):
    """Test we handle unknown error at startup."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.blink.config_flow.Auth.startup",
        side_effect=KeyError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"username": "blink@example.com", "password": "example"}
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "unknown"}


async def test_reauth_shows_user_step(hass):
    """Test reauth shows the user form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_REAUTH},
        data={"username": "blink@example.com", "password": "invalid_password"},
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_options_flow(hass):
    """Test config flow options."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"username": "blink@example.com", "password": "example"},
        options={},
        entry_id=1,
        version=3,
    )
    config_entry.add_to_hass(hass)

    mock_auth = Mock(
        startup=Mock(return_value=True), check_key_required=Mock(return_value=False)
    )
    mock_blink = Mock()

    with patch("homeassistant.components.blink.Auth", return_value=mock_auth), patch(
        "homeassistant.components.blink.Blink", return_value=mock_blink
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(
        config_entry.entry_id, context={"show_advanced_options": False}
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "simple_options"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"scan_interval": 5},
    )

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"] == {"scan_interval": 5}
    assert mock_blink.refresh_rate == 5
