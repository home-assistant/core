"""Tests for cloud tts."""
from collections.abc import Callable, Coroutine
from http import HTTPStatus
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from hass_nabucasa.voice import MAP_VOICE, VoiceError
import pytest
import voluptuous as vol

from homeassistant.components.cloud import DOMAIN, const, tts
from homeassistant.components.tts import DOMAIN as TTS_DOMAIN
from homeassistant.components.tts.helper import get_engine_instance
from homeassistant.config import async_process_ha_core_config
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.typing import ClientSessionGenerator


@pytest.fixture(autouse=True)
async def internal_url_mock(hass: HomeAssistant) -> None:
    """Mock internal URL of the instance."""
    await async_process_ha_core_config(
        hass,
        {"internal_url": "http://example.local:8123"},
    )


def test_default_exists() -> None:
    """Test our default language exists."""
    assert const.DEFAULT_TTS_DEFAULT_VOICE in MAP_VOICE


def test_schema() -> None:
    """Test schema."""
    assert "nl-NL" in tts.SUPPORT_LANGUAGES

    processed = tts.PLATFORM_SCHEMA({"platform": "cloud", "language": "nl-NL"})
    assert processed["gender"] == "female"

    with pytest.raises(vol.Invalid):
        tts.PLATFORM_SCHEMA(
            {"platform": "cloud", "language": "non-existing", "gender": "female"}
        )

    with pytest.raises(vol.Invalid):
        tts.PLATFORM_SCHEMA(
            {"platform": "cloud", "language": "nl-NL", "gender": "not-supported"}
        )

    # Should not raise
    tts.PLATFORM_SCHEMA({"platform": "cloud", "language": "nl-NL", "gender": "female"})
    tts.PLATFORM_SCHEMA({"platform": "cloud"})


@pytest.mark.parametrize(
    ("engine_id", "platform_config"),
    [
        (
            DOMAIN,
            None,
        ),
        (
            DOMAIN,
            {
                "platform": DOMAIN,
                "service_name": "yaml",
                "language": "fr-FR",
                "gender": "female",
            },
        ),
    ],
)
async def test_prefs_default_voice(
    hass: HomeAssistant,
    cloud: MagicMock,
    set_cloud_prefs: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
    engine_id: str,
    platform_config: dict[str, Any] | None,
) -> None:
    """Test cloud provider uses the preferences."""
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, TTS_DOMAIN, {TTS_DOMAIN: platform_config})
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()

    assert cloud.client.prefs.tts_default_voice == ("en-US", "female")

    on_start_callback = cloud.register_on_start.call_args[0][0]
    await on_start_callback()

    engine = get_engine_instance(hass, engine_id)

    assert engine is not None
    # The platform config provider will be overridden by the discovery info provider.
    assert engine.default_language == "en-US"
    assert engine.default_options == {"gender": "female", "audio_output": "mp3"}

    await set_cloud_prefs({"tts_default_voice": ("nl-NL", "male")})
    await hass.async_block_till_done()

    assert engine.default_language == "nl-NL"
    assert engine.default_options == {"gender": "male", "audio_output": "mp3"}


async def test_provider_properties(
    hass: HomeAssistant,
    cloud: MagicMock,
) -> None:
    """Test cloud provider."""
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()
    on_start_callback = cloud.register_on_start.call_args[0][0]
    await on_start_callback()

    engine = get_engine_instance(hass, DOMAIN)

    assert engine is not None
    assert engine.supported_options == ["gender", "voice", "audio_output"]
    assert "nl-NL" in engine.supported_languages
    supported_voices = engine.async_get_supported_voices("nl-NL")
    assert supported_voices is not None
    assert tts.Voice("ColetteNeural", "ColetteNeural") in supported_voices
    supported_voices = engine.async_get_supported_voices("missing_language")
    assert supported_voices is None


@pytest.mark.parametrize(
    ("data", "expected_url_suffix"),
    [
        ({"platform": DOMAIN}, DOMAIN),
        ({"engine_id": DOMAIN}, DOMAIN),
    ],
)
@pytest.mark.parametrize(
    ("mock_process_tts_return_value", "mock_process_tts_side_effect"),
    [
        (b"", None),
        (None, VoiceError("Boom!")),
    ],
)
async def test_get_tts_audio(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    cloud: MagicMock,
    data: dict[str, Any],
    expected_url_suffix: str,
    mock_process_tts_return_value: bytes | None,
    mock_process_tts_side_effect: Exception | None,
) -> None:
    """Test cloud provider."""
    mock_process_tts = AsyncMock(
        return_value=mock_process_tts_return_value,
        side_effect=mock_process_tts_side_effect,
    )
    cloud.voice.process_tts = mock_process_tts
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()
    on_start_callback = cloud.register_on_start.call_args[0][0]
    await on_start_callback()
    client = await hass_client()

    url = "/api/tts_get_url"
    data |= {"message": "There is someone at the door."}

    req = await client.post(url, json=data)
    assert req.status == HTTPStatus.OK
    response = await req.json()

    assert response == {
        "url": (
            "http://example.local:8123/api/tts_proxy/"
            "42f18378fd4393d18c8dd11d03fa9563c1e54491"
            f"_en-us_e09b5a0968_{expected_url_suffix}.mp3"
        ),
        "path": (
            "/api/tts_proxy/42f18378fd4393d18c8dd11d03fa9563c1e54491"
            f"_en-us_e09b5a0968_{expected_url_suffix}.mp3"
        ),
    }
    await hass.async_block_till_done()

    assert mock_process_tts.call_count == 1
    assert mock_process_tts.call_args is not None
    assert mock_process_tts.call_args.kwargs["text"] == "There is someone at the door."
    assert mock_process_tts.call_args.kwargs["language"] == "en-US"
    assert mock_process_tts.call_args.kwargs["gender"] == "female"
    assert mock_process_tts.call_args.kwargs["output"] == "mp3"
