"""Test the AI Speaker config flow."""
from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.ai_speaker.config_flow import InvalidAuth
from homeassistant.components.ai_speaker.const import DOMAIN


async def test_step_user(hass):
    """Test that the user set up form is served."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
    )

    assert result["step_id"] == "user"
    assert result["type"] == "form"
    assert result["errors"] is None


async def test_form_invalid_auth(hass):
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.ai_speaker.config_flow.AisDevice.get_gate_info",
        side_effect=InvalidAuth,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": "1.1.1.1"}
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_cannot_connect(hass):
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.ai_speaker.config_flow.AisDevice.get_gate_info",
        side_effect=InvalidAuth,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": "1.1.1.1"}
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}
