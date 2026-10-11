"""Test Azure OpenAI diagnostics."""

import json

from homeassistant.components.azure_openai.const import (
    CONF_IMAGE_DEPLOYMENT,
    CONF_MODEL_FAMILY,
    CONF_WEB_SEARCH_CITY,
    CONF_WEB_SEARCH_COUNTRY,
    CONF_WEB_SEARCH_REGION,
    CONF_WEB_SEARCH_TIMEZONE,
)
from homeassistant.const import CONF_PROMPT
from homeassistant.core import HomeAssistant

from .conftest import MOCK_CHAT_DEPLOYMENT, MOCK_STT_DEPLOYMENT, MOCK_TTS_DEPLOYMENT

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_init_component: None,
) -> None:
    """Test config entry diagnostics."""
    conversation_subentry = next(
        subentry
        for subentry in mock_config_entry.subentries.values()
        if subentry.subentry_type == "conversation"
    )
    hass.config_entries.async_update_subentry(
        mock_config_entry,
        conversation_subentry,
        data={
            **conversation_subentry.data,
            CONF_PROMPT: "Private instructions",
            CONF_IMAGE_DEPLOYMENT: "private-image-deployment",
            CONF_WEB_SEARCH_CITY: "Private city",
            CONF_WEB_SEARCH_REGION: "Private region",
            CONF_WEB_SEARCH_COUNTRY: "Private country",
            CONF_WEB_SEARCH_TIMEZONE: "Private timezone",
        },
    )
    await hass.async_block_till_done()

    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    assert diagnostics["client"].startswith("openai==")
    assert diagnostics["state"] == "loaded"
    assert diagnostics["title"] == mock_config_entry.title
    assert diagnostics["entry_id"] == mock_config_entry.entry_id
    assert diagnostics["data"] == {
        "api_key": "**REDACTED**",
        "base_url": "**REDACTED**",
    }
    assert set(diagnostics["subentries"]) == set(mock_config_entry.subentries)
    assert set(diagnostics["entities"]) == {
        "ai_task.azure_openai_ai_task",
        "conversation.azure_openai_conversation",
        "stt.azure_openai_stt",
        "tts.azure_openai_tts_text_to_speech",
    }
    assert {
        entity["config_subentry_id"] for entity in diagnostics["entities"].values()
    } == set(mock_config_entry.subentries)

    serialized = json.dumps(diagnostics)
    for private_value in (
        "bla",
        "https://example.openai.azure.com/openai/v1/",
        MOCK_CHAT_DEPLOYMENT,
        MOCK_STT_DEPLOYMENT,
        MOCK_TTS_DEPLOYMENT,
        "Private instructions",
        "private-image-deployment",
        "Private city",
        "Private region",
        "Private country",
        "Private timezone",
    ):
        assert private_value not in serialized

    assert conversation_subentry.data[CONF_MODEL_FAMILY] in serialized
