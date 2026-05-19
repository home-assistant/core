"""Tests for the FlowSpeech config flow."""

from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.flowspeech.const import CONF_API_KEY, CONF_VOICE, DOMAIN
from homeassistant.data_entry_flow import FlowResultType


async def test_form(hass):
    """Test that the form is served."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_create_entry(hass):
    """Test creating a config entry."""
    with (
        patch("flowspeech_sdk.FlowSpeechClient.get_quota", return_value={"remaining": 100}),
        patch("homeassistant.components.flowspeech.async_setup_entry", return_value=True),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={CONF_API_KEY: "fs_test", CONF_VOICE: "Kore"},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "FlowSpeech"
    assert result["data"] == {CONF_API_KEY: "fs_test", CONF_VOICE: "Kore"}
