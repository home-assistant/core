"""Tests for the config_flow of the twinly component."""

from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.twinkly.const import (
    CONF_ENTRY_HOST,
    CONF_ENTRY_ID,
    CONF_ENTRY_MODEL,
    CONF_ENTRY_NAME,
    DOMAIN as TWINKLY_DOMAIN,
)

from tests.components.twinkly import TEST_MODEL, ClientMock


async def test_invalid_host(hass):
    """Test the failure when invalid host provided."""
    result = await hass.config_entries.flow.async_init(
        TWINKLY_DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_ENTRY_HOST: "dummy"},
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {CONF_ENTRY_HOST: "cannot_connect"}


async def test_success_flow(hass):
    """Test that an entity is created when the flow completes."""
    client = ClientMock()
    with patch("twinkly_client.TwinklyClient", return_value=client):
        result = await hass.config_entries.flow.async_init(
            TWINKLY_DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] == "form"
        assert result["step_id"] == "user"
        assert result["errors"] == {}

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_ENTRY_HOST: "dummy"},
        )

    assert result["type"] == "create_entry"
    assert result["title"] == client.id
    assert result["data"] == {
        CONF_ENTRY_HOST: "dummy",
        CONF_ENTRY_ID: client.id,
        CONF_ENTRY_NAME: client.id,
        CONF_ENTRY_MODEL: TEST_MODEL,
    }
