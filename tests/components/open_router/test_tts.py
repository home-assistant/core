"""Test the OpenRouter TTS entity."""

from homeassistant.components.open_router.const import CONF_TTS_VOICE, DOMAIN
from homeassistant.components.open_router.tts import OpenRouterTTSEntity
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.const import CONF_API_KEY, CONF_MODEL
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_default_options_use_configured_voice(
    hass: HomeAssistant,
) -> None:
    """Test the configured voice is used when model voices are available."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "bla"},
        subentries_data=[
            ConfigSubentryData(
                data={
                    CONF_MODEL: "openai/gpt-4o-mini-tts",
                    "supported_voices": ["alloy", "echo"],
                    CONF_TTS_VOICE: "echo",
                },
                subentry_id="tts_subentry",
                subentry_type="tts",
                title="OpenRouter TTS",
                unique_id=None,
            )
        ],
    )
    entry.add_to_hass(hass)

    entity = OpenRouterTTSEntity(entry, entry.subentries["tts_subentry"])

    assert entity.default_options == {"voice": "echo", "preferred_format": "mp3"}
