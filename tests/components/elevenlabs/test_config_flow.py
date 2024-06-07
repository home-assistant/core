"""Test the ElevenLabs text-to-speech config flow."""

from unittest.mock import AsyncMock

from homeassistant import config_entries
from homeassistant.components.elevenlabs.const import CONF_MODEL, CONF_VOICE, DOMAIN
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_user_step(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_async_client: AsyncMock,
) -> None:
    """Test user step create entry result."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_API_KEY: "api_key",
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_VOICE: "voice1",
            CONF_MODEL: "model1",
        },
    )

    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Model 1"
    assert result["data"] == {
        CONF_API_KEY: "api_key",
        CONF_VOICE: "voice1",
        CONF_MODEL: "model1",
    }

    mock_setup_entry.assert_called_once()
    mock_async_client.assert_called_once_with(api_key="api_key")


async def test_invalid_api_key(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_async_client_fail: AsyncMock
) -> None:
    """Test user step with invalid api key."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_API_KEY: "api_key",
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is not None

    mock_setup_entry.assert_not_called()
