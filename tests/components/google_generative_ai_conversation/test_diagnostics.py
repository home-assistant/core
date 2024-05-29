"""Tests for the diagnostics data provided by the Google Generative AI Conversation integration."""

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.google_generative_ai_conversation.const import (
    CONF_CHAT_MODEL,
    CONF_DANGEROUS_BLOCK_THRESHOLD,
    CONF_HARASSMENT_BLOCK_THRESHOLD,
    CONF_HATE_BLOCK_THRESHOLD,
    CONF_MAX_TOKENS,
    CONF_PROMPT,
    CONF_RECOMMENDED,
    CONF_SEXUAL_BLOCK_THRESHOLD,
    CONF_TEMPERATURE,
    CONF_TOP_K,
    CONF_TOP_P,
    RECOMMENDED_CHAT_MODEL,
    RECOMMENDED_HARM_BLOCK_THRESHOLD,
    RECOMMENDED_MAX_TOKENS,
    RECOMMENDED_TEMPERATURE,
    RECOMMENDED_TOP_K,
    RECOMMENDED_TOP_P,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={
            CONF_RECOMMENDED: False,
            CONF_PROMPT: "Speak like a pirate",
            CONF_TEMPERATURE: RECOMMENDED_TEMPERATURE,
            CONF_CHAT_MODEL: RECOMMENDED_CHAT_MODEL,
            CONF_TOP_P: RECOMMENDED_TOP_P,
            CONF_TOP_K: RECOMMENDED_TOP_K,
            CONF_MAX_TOKENS: RECOMMENDED_MAX_TOKENS,
            CONF_HARASSMENT_BLOCK_THRESHOLD: RECOMMENDED_HARM_BLOCK_THRESHOLD,
            CONF_HATE_BLOCK_THRESHOLD: RECOMMENDED_HARM_BLOCK_THRESHOLD,
            CONF_SEXUAL_BLOCK_THRESHOLD: RECOMMENDED_HARM_BLOCK_THRESHOLD,
            CONF_DANGEROUS_BLOCK_THRESHOLD: RECOMMENDED_HARM_BLOCK_THRESHOLD,
        },
    )
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, mock_config_entry)
        == snapshot
    )
