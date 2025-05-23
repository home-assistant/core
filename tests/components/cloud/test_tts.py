"""Tests for cloud tts."""

from collections.abc import AsyncGenerator, Callable, Coroutine
from copy import deepcopy
from http import HTTPStatus
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from hass_nabucasa.voice import VoiceError, VoiceTokenError
from hass_nabucasa.voice_data import TTS_VOICES
import pytest
import voluptuous as vol

from homeassistant.components.assist_pipeline.pipeline import STORAGE_KEY
from homeassistant.components.cloud.const import DEFAULT_TTS_DEFAULT_VOICE, DOMAIN
from homeassistant.components.cloud.tts import (
    DEFAULT_VOICES,
    PLATFORM_SCHEMA,
    SUPPORT_LANGUAGES,
    Voice,
)
from homeassistant.components.media_player import (
    ATTR_MEDIA_CONTENT_ID,
    DOMAIN as DOMAIN_MP,
    SERVICE_PLAY_MEDIA,
)
from homeassistant.components.tts import (
    ATTR_LANGUAGE,
    ATTR_MEDIA_PLAYER_ENTITY_ID,
    ATTR_MESSAGE,
    DOMAIN as TTS_DOMAIN,
    get_engine_instance,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.core_config import async_process_ha_core_config
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.entity_registry import EntityRegistry
from homeassistant.setup import async_setup_component

from . import PIPELINE_DATA

from tests.common import async_mock_service
from tests.components.tts.common import get_media_source_url
from tests.typing import ClientSessionGenerator


@pytest.fixture(autouse=True)
async def delay_save_fixture() -> AsyncGenerator[None]:
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
    assert DEFAULT_TTS_DEFAULT_VOICE[0] in TTS_VOICES
    assert DEFAULT_TTS_DEFAULT_VOICE[1] in TTS_VOICES[DEFAULT_TTS_DEFAULT_VOICE[0]]


def test_all_languages_have_default() -> None:
    """Test all languages have a default voice."""
    assert set(SUPPORT_LANGUAGES).difference(DEFAULT_VOICES) == set()
    assert set(DEFAULT_VOICES).difference(SUPPORT_LANGUAGES) == set()


@pytest.mark.parametrize(("language", "voice"), DEFAULT_VOICES.items())
def test_default_voice_is_valid(language: str, voice: str) -> None:
    """Test that the default voice is valid."""
    assert language in TTS_VOICES
    assert voice in TTS_VOICES[language]


def test_schema() -> None:
    """Test schema."""
    assert "nl-NL" in SUPPORT_LANGUAGES

    processed = PLATFORM_SCHEMA({"platform": "cloud", "language": "nl-NL"})
    assert processed["gender"] == "female"

    with pytest.raises(vol.Invalid):
        PLATFORM_SCHEMA(
            {"platform": "cloud", "language": "non-existing", "gender": "female"}
        )

    with pytest.raises(vol.Invalid):
        PLATFORM_SCHEMA(
            {"platform": "cloud", "language": "nl-NL", "gender": "not-supported"}
        )

    # Should not raise
    PLATFORM_SCHEMA({"platform": "cloud", "language": "nl-NL", "gender": "female"})
    PLATFORM_SCHEMA({"platform": "cloud"})


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
    await hass.async_block_till_done()
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()

    assert cloud.client.prefs.tts_default_voice == ("en-US", "JennyNeural")

    on_start_callback = cloud.register_on_start.call_args[0][0]
    await on_start_callback()
    await hass.async_block_till_done()

    engine = get_engine_instance(hass, engine_id)

    assert engine is not None
    # The platform config provider will be overridden by the discovery info provider.
    assert engine.default_language == "en-US"
    assert engine.default_options == {"audio_output": "mp3"}

    await set_cloud_prefs({"tts_default_voice": ("nl-NL", "MaartenNeural")})
    await hass.async_block_till_done()

    assert engine.default_language == "nl-NL"
    assert engine.default_options == {"audio_output": "mp3"}


async def test_deprecated_platform_config(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    cloud: MagicMock,
) -> None:
    """Test cloud provider uses the preferences."""
    assert await async_setup_component(
        hass, TTS_DOMAIN, {TTS_DOMAIN: {"platform": DOMAIN}}
    )
    await hass.async_block_till_done()

    issue = issue_registry.async_get_issue(DOMAIN, "deprecated_tts_platform_config")
    assert issue is not None
    assert issue.breaks_in_ha_version == "2024.9.0"
    assert issue.is_fixable is False
    assert issue.is_persistent is False
    assert issue.severity == ir.IssueSeverity.WARNING
    assert issue.translation_key == "deprecated_tts_platform_config"


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
    assert Voice("ColetteNeural", "Colette") in supported_voices
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

    with patch(
        "homeassistant.components.tts.secrets.token_urlsafe", return_value="test_token"
    ):
        url = "/api/tts_get_url"
        data |= {"message": "There is someone at the door."}

        req = await client.post(url, json=data)
        assert req.status == HTTPStatus.OK
        response = await req.json()

        assert response == {
            "url": ("http://example.local:8123/api/tts_proxy/test_token.mp3"),
            "path": ("/api/tts_proxy/test_token.mp3"),
        }
        await hass.async_block_till_done()

    assert mock_process_tts.call_count == 1
    assert mock_process_tts.call_args is not None
    assert mock_process_tts.call_args.kwargs["text"] == "There is someone at the door."
    assert mock_process_tts.call_args.kwargs["language"] == "en-US"
    assert mock_process_tts.call_args.kwargs["gender"] is None
    assert mock_process_tts.call_args.kwargs["voice"] == "JennyNeural"
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

    with patch(
        "homeassistant.components.tts.secrets.token_urlsafe", return_value="test_token"
    ):
        url = "/api/tts_get_url"
        data |= {"message": "There is someone at the door."}

        req = await client.post(url, json=data)
        assert req.status == HTTPStatus.OK
        response = await req.json()

        assert response == {
            "url": ("http://example.local:8123/api/tts_proxy/test_token.mp3"),
            "path": ("/api/tts_proxy/test_token.mp3"),
        }
        await hass.async_block_till_done()

    assert mock_process_tts.call_count == 1
    assert mock_process_tts.call_args is not None
    assert mock_process_tts.call_args.kwargs["text"] == "There is someone at the door."
    assert mock_process_tts.call_args.kwargs["language"] == "en-US"
    assert mock_process_tts.call_args.kwargs["gender"] is None
    assert mock_process_tts.call_args.kwargs["voice"] == "JennyNeural"
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

    with patch(
        "homeassistant.components.tts.secrets.token_urlsafe", return_value="test_token"
    ):
        url = "/api/tts_get_url"
        data = {
            "engine_id": entity_id,
            "message": "There is someone at the door.",
        }

        req = await client.post(url, json=data)
        assert req.status == HTTPStatus.OK
        response = await req.json()

        assert response == {
            "url": ("http://example.local:8123/api/tts_proxy/test_token.mp3"),
            "path": ("/api/tts_proxy/test_token.mp3"),
        }
        await hass.async_block_till_done()

    assert mock_process_tts.call_count == 1
    assert mock_process_tts.call_args is not None
    assert mock_process_tts.call_args.kwargs["text"] == "There is someone at the door."
    assert mock_process_tts.call_args.kwargs["language"] == "en-US"
    assert mock_process_tts.call_args.kwargs["gender"] is None
    assert mock_process_tts.call_args.kwargs["voice"] == "JennyNeural"
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
    issue_registry: ir.IssueRegistry,
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
    with patch(
        "homeassistant.components.tts.secrets.token_urlsafe", return_value="test_token"
    ):
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
            "url": ("http://example.local:8123/api/tts_proxy/test_token.mp3"),
            "path": ("/api/tts_proxy/test_token.mp3"),
        }
        await hass.async_block_till_done()

    assert mock_process_tts.call_count == 1
    assert mock_process_tts.call_args is not None
    assert mock_process_tts.call_args.kwargs["text"] == "There is someone at the door."
    assert mock_process_tts.call_args.kwargs["language"] == language
    assert mock_process_tts.call_args.kwargs["gender"] is None
    assert mock_process_tts.call_args.kwargs["voice"] == replacement_voice
    assert mock_process_tts.call_args.kwargs["output"] == "mp3"
    issue = issue_registry.async_get_issue(
        "cloud", f"deprecated_voice_{replacement_voice}"
    )
    assert issue is None
    mock_process_tts.reset_mock()

    # Test with deprecated voice.
    data["options"] = {"voice": deprecated_voice}

    with patch(
        "homeassistant.components.tts.secrets.token_urlsafe", return_value="test_token"
    ):
        req = await client.post(url, json=data)
        assert req.status == HTTPStatus.OK
        response = await req.json()

        assert response == {
            "url": ("http://example.local:8123/api/tts_proxy/test_token.mp3"),
            "path": ("/api/tts_proxy/test_token.mp3"),
        }
        await hass.async_block_till_done()

    issue_id = f"deprecated_voice_{deprecated_voice}"

    assert mock_process_tts.call_count == 1
    assert mock_process_tts.call_args is not None
    assert mock_process_tts.call_args.kwargs["text"] == "There is someone at the door."
    assert mock_process_tts.call_args.kwargs["language"] == language
    assert mock_process_tts.call_args.kwargs["gender"] is None
    assert mock_process_tts.call_args.kwargs["voice"] == replacement_voice
    assert mock_process_tts.call_args.kwargs["output"] == "mp3"
    issue = issue_registry.async_get_issue("cloud", issue_id)
    assert issue is not None
    assert issue.breaks_in_ha_version == "2024.8.0"
    assert issue.is_fixable is True
    assert issue.is_persistent is True
    assert issue.severity == ir.IssueSeverity.WARNING
    assert issue.translation_key == "deprecated_voice"
    assert issue.translation_placeholders == {
        "deprecated_voice": deprecated_voice,
        "replacement_voice": replacement_voice,
    }

    resp = await client.post(
        "/api/repairs/issues/fix",
        json={"handler": DOMAIN, "issue_id": issue.issue_id},
    )

    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    flow_id = data["flow_id"]
    assert data == {
        "type": "form",
        "flow_id": flow_id,
        "handler": DOMAIN,
        "step_id": "confirm",
        "data_schema": [],
        "errors": None,
        "description_placeholders": {
            "deprecated_voice": "XiaoxuanNeural",
            "replacement_voice": "XiaozhenNeural",
        },
        "last_step": None,
        "preview": None,
    }

    resp = await client.post(f"/api/repairs/issues/fix/{flow_id}")

    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    flow_id = data["flow_id"]
    assert data == {
        "type": "create_entry",
        "flow_id": flow_id,
        "handler": DOMAIN,
        "description": None,
        "description_placeholders": None,
    }

    assert not issue_registry.async_get_issue(DOMAIN, issue_id)


@pytest.mark.parametrize(
    ("data", "expected_url_suffix"),
    [
        ({"platform": DOMAIN}, DOMAIN),
        ({"engine_id": DOMAIN}, DOMAIN),
        ({"engine_id": "tts.home_assistant_cloud"}, "tts.home_assistant_cloud"),
    ],
)
async def test_deprecated_gender(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    cloud: MagicMock,
    hass_client: ClientSessionGenerator,
    data: dict[str, Any],
    expected_url_suffix: str,
) -> None:
    """Test we create an issue when a deprecated gender is used for text-to-speech."""
    language = "zh-CN"
    gender_option = "male"
    mock_process_tts = AsyncMock(
        return_value=b"",
    )
    cloud.voice.process_tts = mock_process_tts

    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()
    await cloud.login("test-user", "test-pass")
    client = await hass_client()

    # Test without deprecated gender option.
    with patch(
        "homeassistant.components.tts.secrets.token_urlsafe", return_value="test_token"
    ):
        url = "/api/tts_get_url"
        data |= {
            "message": "There is someone at the door.",
            "language": language,
        }

        req = await client.post(url, json=data)
        assert req.status == HTTPStatus.OK
        response = await req.json()

        assert response == {
            "url": ("http://example.local:8123/api/tts_proxy/test_token.mp3"),
            "path": ("/api/tts_proxy/test_token.mp3"),
        }
        await hass.async_block_till_done()

    assert mock_process_tts.call_count == 1
    assert mock_process_tts.call_args is not None
    assert mock_process_tts.call_args.kwargs["text"] == "There is someone at the door."
    assert mock_process_tts.call_args.kwargs["language"] == language
    assert mock_process_tts.call_args.kwargs["voice"] == "XiaoxiaoNeural"
    assert mock_process_tts.call_args.kwargs["output"] == "mp3"
    issue = issue_registry.async_get_issue("cloud", "deprecated_gender")
    assert issue is None
    mock_process_tts.reset_mock()

    # Test with deprecated gender option.
    data["options"] = {"gender": gender_option}

    with patch(
        "homeassistant.components.tts.secrets.token_urlsafe", return_value="test_token"
    ):
        req = await client.post(url, json=data)
        assert req.status == HTTPStatus.OK
        response = await req.json()

        assert response == {
            "url": ("http://example.local:8123/api/tts_proxy/test_token.mp3"),
            "path": ("/api/tts_proxy/test_token.mp3"),
        }
        await hass.async_block_till_done()

    issue_id = "deprecated_gender"

    assert mock_process_tts.call_count == 1
    assert mock_process_tts.call_args is not None
    assert mock_process_tts.call_args.kwargs["text"] == "There is someone at the door."
    assert mock_process_tts.call_args.kwargs["language"] == language
    assert mock_process_tts.call_args.kwargs["gender"] == gender_option
    assert mock_process_tts.call_args.kwargs["voice"] == "XiaoxiaoNeural"
    assert mock_process_tts.call_args.kwargs["output"] == "mp3"
    issue = issue_registry.async_get_issue("cloud", issue_id)
    assert issue is not None
    assert issue.breaks_in_ha_version == "2024.10.0"
    assert issue.is_fixable is True
    assert issue.is_persistent is True
    assert issue.severity == ir.IssueSeverity.WARNING
    assert issue.translation_key == "deprecated_gender"
    assert issue.translation_placeholders == {
        "integration_name": "Home Assistant Cloud",
        "deprecated_option": "gender",
        "replacement_option": "voice",
    }

    resp = await client.post(
        "/api/repairs/issues/fix",
        json={"handler": DOMAIN, "issue_id": issue.issue_id},
    )

    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    flow_id = data["flow_id"]
    assert data == {
        "type": "form",
        "flow_id": flow_id,
        "handler": DOMAIN,
        "step_id": "confirm",
        "data_schema": [],
        "errors": None,
        "description_placeholders": {
            "integration_name": "Home Assistant Cloud",
            "deprecated_option": "gender",
            "replacement_option": "voice",
        },
        "last_step": None,
        "preview": None,
    }

    resp = await client.post(f"/api/repairs/issues/fix/{flow_id}")

    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    flow_id = data["flow_id"]
    assert data == {
        "type": "create_entry",
        "flow_id": flow_id,
        "handler": DOMAIN,
        "description": None,
        "description_placeholders": None,
    }

    assert not issue_registry.async_get_issue(DOMAIN, issue_id)


@pytest.mark.parametrize(
    ("service", "service_data"),
    [
        (
            "speak",
            {
                ATTR_ENTITY_ID: "tts.home_assistant_cloud",
                ATTR_LANGUAGE: "id-ID",
                ATTR_MEDIA_PLAYER_ENTITY_ID: "media_player.something",
                ATTR_MESSAGE: "There is someone at the door.",
            },
        ),
        (
            "cloud_say",
            {
                ATTR_ENTITY_ID: "media_player.something",
                ATTR_LANGUAGE: "id-ID",
                ATTR_MESSAGE: "There is someone at the door.",
            },
        ),
    ],
)
async def test_tts_services(
    hass: HomeAssistant,
    cloud: MagicMock,
    hass_client: ClientSessionGenerator,
    service: str,
    service_data: dict[str, Any],
) -> None:
    """Test tts services."""
    calls = async_mock_service(hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)
    mock_process_tts = AsyncMock(return_value=b"")
    cloud.voice.process_tts = mock_process_tts

    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()
    await cloud.login("test-user", "test-pass")
    client = await hass_client()

    await hass.services.async_call(
        domain=TTS_DOMAIN,
        service=service,
        service_data=service_data,
        blocking=True,
    )

    assert len(calls) == 1

    url = await get_media_source_url(hass, calls[0].data[ATTR_MEDIA_CONTENT_ID])
    await hass.async_block_till_done()
    response = await client.get(url)
    assert response.status == HTTPStatus.OK
    await hass.async_block_till_done()

    assert mock_process_tts.call_count == 1
    assert mock_process_tts.call_args is not None
    assert mock_process_tts.call_args.kwargs["text"] == "There is someone at the door."
    assert mock_process_tts.call_args.kwargs["language"] == service_data[ATTR_LANGUAGE]
    assert mock_process_tts.call_args.kwargs["voice"] == "GadisNeural"
    assert mock_process_tts.call_args.kwargs["output"] == "mp3"
