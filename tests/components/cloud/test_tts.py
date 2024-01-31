"""Tests for cloud tts."""
from collections.abc import AsyncGenerator, Callable, Coroutine
from copy import deepcopy
from http import HTTPStatus
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from hass_nabucasa.voice import MAP_VOICE, VoiceError, VoiceTokenError
import pytest
import voluptuous as vol

from homeassistant.components.assist_pipeline.pipeline import STORAGE_KEY
from homeassistant.components.cloud import DOMAIN, const, tts
from homeassistant.components.tts import DOMAIN as TTS_DOMAIN
from homeassistant.components.tts.helper import get_engine_instance
from homeassistant.config import async_process_ha_core_config
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import EntityRegistry
from homeassistant.helpers.issue_registry import IssueRegistry, IssueSeverity
from homeassistant.setup import async_setup_component

from . import PIPELINE_DATA

from tests.typing import ClientSessionGenerator


@pytest.fixture(autouse=True)
async def delay_save_fixture() -> AsyncGenerator[None, None]:
    """Load the homeassistant integration."""
    with patch("homeassistant.helpers.collection.SAVE_DELAY", new=0):
        yield


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
        (
            "tts.home_assistant_cloud",
            None,
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


@pytest.mark.parametrize(
    "engine_id",
    [
        DOMAIN,
        "tts.home_assistant_cloud",
    ],
)
async def test_provider_properties(
    hass: HomeAssistant,
    cloud: MagicMock,
    engine_id: str,
) -> None:
    """Test cloud provider."""
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()
    on_start_callback = cloud.register_on_start.call_args[0][0]
    await on_start_callback()

    engine = get_engine_instance(hass, engine_id)

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
        ({"engine_id": "tts.home_assistant_cloud"}, "tts.home_assistant_cloud"),
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


@pytest.mark.parametrize(
    ("data", "expected_url_suffix"),
    [
        ({"platform": DOMAIN}, DOMAIN),
        ({"engine_id": DOMAIN}, DOMAIN),
    ],
)
async def test_get_tts_audio_logged_out(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    cloud: MagicMock,
    data: dict[str, Any],
    expected_url_suffix: str,
) -> None:
    """Test cloud get tts audio when user is logged out."""
    mock_process_tts = AsyncMock(
        side_effect=VoiceTokenError("No token!"),
    )
    cloud.voice.process_tts = mock_process_tts
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()
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


@pytest.mark.parametrize(
    ("mock_process_tts_return_value", "mock_process_tts_side_effect"),
    [
        (b"", None),
        (None, VoiceError("Boom!")),
    ],
)
async def test_tts_entity(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    entity_registry: EntityRegistry,
    cloud: MagicMock,
    mock_process_tts_return_value: bytes | None,
    mock_process_tts_side_effect: Exception | None,
) -> None:
    """Test text-to-speech entity."""
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
    entity_id = "tts.home_assistant_cloud"

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNKNOWN

    url = "/api/tts_get_url"
    data = {
        "engine_id": entity_id,
        "message": "There is someone at the door.",
    }

    req = await client.post(url, json=data)
    assert req.status == HTTPStatus.OK
    response = await req.json()

    assert response == {
        "url": (
            "http://example.local:8123/api/tts_proxy/"
            "42f18378fd4393d18c8dd11d03fa9563c1e54491"
            f"_en-us_e09b5a0968_{entity_id}.mp3"
        ),
        "path": (
            "/api/tts_proxy/42f18378fd4393d18c8dd11d03fa9563c1e54491"
            f"_en-us_e09b5a0968_{entity_id}.mp3"
        ),
    }
    await hass.async_block_till_done()

    assert mock_process_tts.call_count == 1
    assert mock_process_tts.call_args is not None
    assert mock_process_tts.call_args.kwargs["text"] == "There is someone at the door."
    assert mock_process_tts.call_args.kwargs["language"] == "en-US"
    assert mock_process_tts.call_args.kwargs["gender"] == "female"
    assert mock_process_tts.call_args.kwargs["output"] == "mp3"

    state = hass.states.get(entity_id)
    assert state
    assert state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN)

    # Test removing the entity
    entity_registry.async_remove(entity_id)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is None


async def test_migrating_pipelines(
    hass: HomeAssistant,
    cloud: MagicMock,
    hass_client: ClientSessionGenerator,
    hass_storage: dict[str, Any],
) -> None:
    """Test migrating pipelines when cloud tts entity is added."""
    entity_id = "tts.home_assistant_cloud"
    mock_process_tts = AsyncMock(
        return_value=b"",
    )
    cloud.voice.process_tts = mock_process_tts
    hass_storage[STORAGE_KEY] = {
        "version": 1,
        "minor_version": 1,
        "key": "assist_pipeline.pipelines",
        "data": deepcopy(PIPELINE_DATA),
    }

    assert await async_setup_component(hass, "assist_pipeline", {})
    assert await async_setup_component(hass, DOMAIN, {"cloud": {}})
    await hass.async_block_till_done()

    await cloud.login("test-user", "test-pass")
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNKNOWN

    # The stt/tts engines should have been updated to the new cloud engine ids.
    assert (
        hass_storage[STORAGE_KEY]["data"]["items"][0]["stt_engine"]
        == "stt.home_assistant_cloud"
    )
    assert hass_storage[STORAGE_KEY]["data"]["items"][0]["tts_engine"] == entity_id

    # The other items should stay the same.
    assert (
        hass_storage[STORAGE_KEY]["data"]["items"][0]["conversation_engine"]
        == "conversation_engine_1"
    )
    assert (
        hass_storage[STORAGE_KEY]["data"]["items"][0]["conversation_language"]
        == "language_1"
    )
    assert (
        hass_storage[STORAGE_KEY]["data"]["items"][0]["id"]
        == "01GX8ZWBAQYWNB1XV3EXEZ75DY"
    )
    assert hass_storage[STORAGE_KEY]["data"]["items"][0]["language"] == "language_1"
    assert (
        hass_storage[STORAGE_KEY]["data"]["items"][0]["name"] == "Home Assistant Cloud"
    )
    assert hass_storage[STORAGE_KEY]["data"]["items"][0]["stt_language"] == "language_1"
    assert hass_storage[STORAGE_KEY]["data"]["items"][0]["tts_language"] == "language_1"
    assert (
        hass_storage[STORAGE_KEY]["data"]["items"][0]["tts_voice"]
        == "Arnold Schwarzenegger"
    )
    assert hass_storage[STORAGE_KEY]["data"]["items"][0]["wake_word_entity"] is None
    assert hass_storage[STORAGE_KEY]["data"]["items"][0]["wake_word_id"] is None
    assert hass_storage[STORAGE_KEY]["data"]["items"][1] == PIPELINE_DATA["items"][1]
    assert hass_storage[STORAGE_KEY]["data"]["items"][2] == PIPELINE_DATA["items"][2]


@pytest.mark.parametrize(
    ("data", "expected_url_suffix"),
    [
        ({"platform": DOMAIN}, DOMAIN),
        ({"engine_id": DOMAIN}, DOMAIN),
        ({"engine_id": "tts.home_assistant_cloud"}, "tts.home_assistant_cloud"),
    ],
)
async def test_deprecated_voice(
    hass: HomeAssistant,
    issue_registry: IssueRegistry,
    cloud: MagicMock,
    hass_client: ClientSessionGenerator,
    data: dict[str, Any],
    expected_url_suffix: str,
) -> None:
    """Test we create an issue when a deprecated voice is used for text-to-speech."""
    language = "zh-CN"
    deprecated_voice = "XiaoxuanNeural"
    replacement_voice = "XiaozhenNeural"
    mock_process_tts = AsyncMock(
        return_value=b"",
    )
    cloud.voice.process_tts = mock_process_tts

    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()
    await cloud.login("test-user", "test-pass")
    client = await hass_client()

    # Test with non deprecated voice.
    url = "/api/tts_get_url"
    data |= {
        "message": "There is someone at the door.",
        "language": language,
        "options": {"voice": replacement_voice},
    }

    req = await client.post(url, json=data)
    assert req.status == HTTPStatus.OK
    response = await req.json()

    assert response == {
        "url": (
            "http://example.local:8123/api/tts_proxy/"
            "42f18378fd4393d18c8dd11d03fa9563c1e54491"
            f"_{language.lower()}_1c4ec2f170_{expected_url_suffix}.mp3"
        ),
        "path": (
            "/api/tts_proxy/42f18378fd4393d18c8dd11d03fa9563c1e54491"
            f"_{language.lower()}_1c4ec2f170_{expected_url_suffix}.mp3"
        ),
    }
    await hass.async_block_till_done()

    assert mock_process_tts.call_count == 1
    assert mock_process_tts.call_args is not None
    assert mock_process_tts.call_args.kwargs["text"] == "There is someone at the door."
    assert mock_process_tts.call_args.kwargs["language"] == language
    assert mock_process_tts.call_args.kwargs["gender"] == "female"
    assert mock_process_tts.call_args.kwargs["voice"] == replacement_voice
    assert mock_process_tts.call_args.kwargs["output"] == "mp3"
    issue = issue_registry.async_get_issue(
        "cloud", f"deprecated_voice_{replacement_voice}"
    )
    assert issue is None
    mock_process_tts.reset_mock()

    # Test with deprecated voice.
    data["options"] = {"voice": deprecated_voice}

    req = await client.post(url, json=data)
    assert req.status == HTTPStatus.OK
    response = await req.json()

    assert response == {
        "url": (
            "http://example.local:8123/api/tts_proxy/"
            "42f18378fd4393d18c8dd11d03fa9563c1e54491"
            f"_{language.lower()}_a1c3b0ac0e_{expected_url_suffix}.mp3"
        ),
        "path": (
            "/api/tts_proxy/42f18378fd4393d18c8dd11d03fa9563c1e54491"
            f"_{language.lower()}_a1c3b0ac0e_{expected_url_suffix}.mp3"
        ),
    }
    await hass.async_block_till_done()

    assert mock_process_tts.call_count == 1
    assert mock_process_tts.call_args is not None
    assert mock_process_tts.call_args.kwargs["text"] == "There is someone at the door."
    assert mock_process_tts.call_args.kwargs["language"] == language
    assert mock_process_tts.call_args.kwargs["gender"] == "female"
    assert mock_process_tts.call_args.kwargs["voice"] == replacement_voice
    assert mock_process_tts.call_args.kwargs["output"] == "mp3"
    issue = issue_registry.async_get_issue(
        "cloud", f"deprecated_voice_{deprecated_voice}"
    )
    assert issue is not None
    assert issue.breaks_in_ha_version == "2024.8.0"
    assert issue.is_fixable is True
    assert issue.is_persistent is True
    assert issue.severity == IssueSeverity.WARNING
    assert issue.translation_key == "deprecated_voice"
    assert issue.translation_placeholders == {
        "deprecated_voice": deprecated_voice,
        "replacement_voice": replacement_voice,
    }
