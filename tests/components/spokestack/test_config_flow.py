"""Spokestack config flow test."""
from unittest.mock import patch

import pytest
from spokestack.tts.clients.spokestack import TTSError

from homeassistant import config_entries
from homeassistant.components.spokestack.const import (
    CONF_IDENTITY,
    CONF_SECRET_KEY,
    DOMAIN,
)
from homeassistant.components.tts import CONF_LANG


@pytest.fixture
def mock_client():
    """Mock TextToSpeechClient."""
    with patch(
        "homeassistant.components.spokestack.tts.TextToSpeechClient"
    ) as mock_client:
        yield mock_client


async def test_form(hass, mock_client):
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.spokestack.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_IDENTITY: "test-key", CONF_SECRET_KEY: "test-secret"},
        )

        assert result["type"] == "create_entry"
        assert result["title"] == "Spokestack"
        assert result["data"] == {
            CONF_IDENTITY: "test-key",
            CONF_SECRET_KEY: "test-secret",
            CONF_LANG: "en-US",
        }
        await hass.async_block_till_done()
        mock_setup_entry.assert_called_once()


async def test_invalid_entry(hass):
    """Test we handle invalid keys."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.spokestack.config_flow.validate_user_input",
        side_effect=TTSError([{"message": "Unauthorized"}]),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_IDENTITY: "invalid-key", CONF_SECRET_KEY: "invalid-secret"},
        )

    assert result["errors"] == {"base": "invalid_config"}
