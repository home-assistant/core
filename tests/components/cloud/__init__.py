"""Tests for the cloud component."""

from typing import Any
from unittest.mock import AsyncMock, patch

from homeassistant.components.cloud.const import (
    DATA_CLOUD,
    DOMAIN,
    PREF_ALEXA_SETTINGS_VERSION,
    PREF_ENABLE_ALEXA,
    PREF_ENABLE_GOOGLE,
    PREF_GOOGLE_SECURE_DEVICES_PIN,
    PREF_GOOGLE_SETTINGS_VERSION,
)
from homeassistant.components.cloud.prefs import (
    ALEXA_SETTINGS_VERSION,
    GOOGLE_SETTINGS_VERSION,
    CloudPreferences,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

PIPELINE_DATA = {
    "items": [
        {
            "conversation_engine": "conversation_engine_1",
            "conversation_language": "language_1",
            "id": "01GX8ZWBAQYWNB1XV3EXEZ75DY",
            "language": "language_1",
            "name": "Home Assistant Cloud",
            "stt_engine": "cloud",
            "stt_language": "language_1",
            "tts_engine": "cloud",
            "tts_language": "language_1",
            "tts_voice": "Arnold Schwarzenegger",
            "wake_word_entity": None,
            "wake_word_id": None,
        },
        {
            "conversation_engine": "conversation_engine_2",
            "conversation_language": "language_2",
            "id": "01GX8ZWBAQTKFQNK4W7Q4CTRCX",
            "language": "language_2",
            "name": "name_2",
            "stt_engine": "stt_engine_2",
            "stt_language": "language_2",
            "tts_engine": "tts_engine_2",
            "tts_language": "language_2",
            "tts_voice": "The Voice",
            "wake_word_entity": None,
            "wake_word_id": None,
        },
        {
            "conversation_engine": "conversation_engine_3",
            "conversation_language": "language_3",
            "id": "01GX8ZWBAQSV1HP3WGJPFWEJ8J",
            "language": "language_3",
            "name": "name_3",
            "stt_engine": None,
            "stt_language": None,
            "tts_engine": None,
            "tts_language": None,
            "tts_voice": None,
            "wake_word_entity": None,
            "wake_word_id": None,
        },
    ],
    "preferred_item": "01GX8ZWBAQYWNB1XV3EXEZ75DY",
}


async def mock_cloud(hass: HomeAssistant, config: dict[str, Any] | None = None) -> None:
    """Mock cloud."""
    # The homeassistant integration is needed by cloud. It's not in it's requirements
    # because it's always setup by bootstrap. Set it up manually in tests.
    assert await async_setup_component(hass, "homeassistant", {})

    assert await async_setup_component(hass, DOMAIN, {"cloud": config or {}})
    cloud_inst = hass.data[DATA_CLOUD]
    with patch("hass_nabucasa.Cloud.run_executor", AsyncMock(return_value=None)):
        await cloud_inst.initialize()


def mock_cloud_prefs(hass: HomeAssistant, prefs: dict[str, Any]) -> CloudPreferences:
    """Fixture for cloud component."""
    prefs_to_set = {
        PREF_ALEXA_SETTINGS_VERSION: ALEXA_SETTINGS_VERSION,
        PREF_ENABLE_ALEXA: True,
        PREF_ENABLE_GOOGLE: True,
        PREF_GOOGLE_SECURE_DEVICES_PIN: None,
        PREF_GOOGLE_SETTINGS_VERSION: GOOGLE_SETTINGS_VERSION,
    }
    prefs_to_set.update(prefs)
    hass.data[DATA_CLOUD].client._prefs._prefs = prefs_to_set
    return hass.data[DATA_CLOUD].client._prefs
