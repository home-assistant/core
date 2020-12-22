"""Test the Cisco Webex config flow."""
from homeassistant import config_entries, setup
from homeassistant.components.cisco_webex.config_flow import (
    CannotConnect,
    EmailNotFound,
    InvalidEmail,
)
from homeassistant.components.cisco_webex.const import DOMAIN

from tests.async_mock import patch


async def test_form(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] is None

    with patch(
        "homeassistant.components.cisco_webex.config_flow.ConfigValidationHub.validate_config",
        return_value=True,
    ), patch(
        "homeassistant.components.cisco_webex.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.cisco_webex.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"token": "asdasdas", "email": "test-email@test.com"},
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "unknown - test-email@test.com"
    assert result2["data"] == {
        "token": "asdasdas",
        "email": "test-email@test.com",
        "display_name": "unknown",
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_email(hass):
    """Test we handle invalid email format."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.cisco_webex.config_flow.ConfigValidationHub.validate_config",
        side_effect=InvalidEmail,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"token": "asdasdas", "email": "test-email"},
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "invalid_email"}


async def test_form_email_not_found(hass):
    """Test we handle email not found."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.cisco_webex.config_flow.ConfigValidationHub.validate_config",
        side_effect=EmailNotFound,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"token": "asdasdas", "email": "test-email@test.com"},
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "email_not_found"}


async def test_form_cannot_connect(hass):
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.cisco_webex.config_flow.ConfigValidationHub.validate_config",
        side_effect=CannotConnect,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"token": "asdasdas", "email": "test-email@test.com"},
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}
