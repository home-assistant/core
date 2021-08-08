"""Spokestack config flow test."""
from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.spokestack.const import (
    CONF_KEY_ID,
    CONF_KEY_SECRET,
    CONF_LANG,
    CONF_MODE,
    CONF_PROFILE,
    CONF_VOICE,
    DOMAIN,
)


async def test_form(hass):
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
            {CONF_KEY_ID: "test-key", CONF_KEY_SECRET: "test-secret"},
        )

        assert result["type"] == "create_entry"
        assert result["title"] == "Spokestack"
        assert result["data"] == {
            CONF_KEY_ID: "test-key",
            CONF_KEY_SECRET: "test-secret",
            CONF_VOICE: "demo-male",
            CONF_LANG: "en-US",
            CONF_MODE: "text",
            CONF_PROFILE: "default",
        }
        await hass.async_block_till_done()
        mock_setup_entry.assert_called_once()
