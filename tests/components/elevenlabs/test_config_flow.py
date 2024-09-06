"""Test the ElevenLabs text-to-speech config flow."""

from unittest.mock import AsyncMock

from homeassistant.components.elevenlabs.const import (
    CONF_MODEL,
    CONF_VOICE,
    DEFAULT_MODEL,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_user_step(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_async_client: AsyncMock,
) -> None:
    """Test user step create entry result."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert not result["errors"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_API_KEY: "api_key",
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "ElevenLabs"
    assert result["data"] == {
        "api_key": "api_key",
    }
    assert result["options"] == {CONF_MODEL: DEFAULT_MODEL, CONF_VOICE: "voice1"}

    mock_setup_entry.assert_called_once()


async def test_invalid_api_key(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_async_client_fail: AsyncMock
) -> None:
    """Test user step with invalid api key."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert not result["errors"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_API_KEY: "api_key",
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"]

    mock_setup_entry.assert_not_called()


async def test_options_flow_init(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_async_client: AsyncMock,
    mock_entry: MockConfigEntry,
) -> None:
    """Test options flow init."""
    mock_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(mock_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_MODEL: "model1", CONF_VOICE: "voice1"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert mock_entry.options == {CONF_MODEL: "model1", CONF_VOICE: "voice1"}

    mock_setup_entry.assert_called_once()
