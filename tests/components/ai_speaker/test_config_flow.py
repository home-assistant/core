"""Test the AI Speaker config flow."""
from homeassistant import config_entries
from homeassistant.components.ai_speaker.config_flow import InvalidAuth
from homeassistant.components.ai_speaker.const import DOMAIN

from tests.common import patch


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
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_unknown_error(hass):
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.ai_speaker.config_flow.AisDevice.get_gate_info",
        side_effect=Exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": "zzz"}
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "unknown"}


async def test_create_entry(hass, aioclient_mock):
    """Test that errors are shown when duplicates are added."""
    aioclient_mock.get(
        "http://ais-dom.local", json={"Product": "AI-Speaker", "ais_id": "dom-1234"}
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={"host": "ais-dom.local"},
    )

    assert result["type"] == "create_entry"
