"""Tests for Microsoft text-to-speech."""

from http import HTTPStatus
from typing import Any
from unittest.mock import MagicMock

import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from pytest_homeassistant.typing import ClientSessionGenerator
from requests.exceptions import ConnectionError as RequestsConnectionError, HTTPError
from syrupy.assertion import SnapshotAssertion

from homeassistant.components import tts
from homeassistant.components.media_player import ATTR_MEDIA_CONTENT_ID
from homeassistant.components.microsoft.const import DOMAIN
from homeassistant.components.microsoft.tts import SUPPORTED_LANGUAGES
from homeassistant.const import ATTR_ENTITY_ID, CONF_API_KEY, CONF_PLATFORM
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError, ServiceNotFound
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.setup import async_setup_component

from . import http_error

from tests.components.tts.common import retrieve_media

ENTITY_ID = "tts.microsoft_text_to_speech"
MEDIA_PLAYER_ENTITY_ID = "media_player.something"
MESSAGE = "There is a person at the front door."

LEGACY_SPEAK_KWARGS = {
    "language": "en-us",
    "gender": "Female",
    "voiceType": "JennyNeural",
    "output": "audio-24khz-96kbitrate-mono-mp3",
    "rate": "0%",
    "volume": "0%",
    "pitch": "default",
    "contour": "",
    "text": MESSAGE,
}

ENTITY_SPEAK_KWARGS = {
    "language": "en-gb",
    "gender": "Female",
    "voiceType": "AbbiNeural",
    "output": "audio-24khz-96kbitrate-mono-mp3",
    "rate": "10%",
    "volume": "-10%",
    "pitch": "high",
    "contour": "(0%,+20Hz)",
    "text": MESSAGE,
}


async def setup_legacy_platform(hass: HomeAssistant, config: dict[str, Any]) -> None:
    """Set up the legacy Microsoft TTS platform from YAML."""
    await async_setup_component(
        hass,
        tts.DOMAIN,
        {tts.DOMAIN: {CONF_PLATFORM: DOMAIN, CONF_API_KEY: "test-api-key", **config}},
    )
    await hass.async_block_till_done()


@pytest.fixture
async def setup_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tts_translator: MagicMock,
) -> None:
    """Set up the Microsoft config entry."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.usefixtures("setup_entry")
async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the text-to-speech entity and its device."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)

    assert device_registry.async_get_device_by_identifier(
        (DOMAIN, mock_config_entry.entry_id), mock_config_entry.entry_id
    ) == snapshot(name="device")


@pytest.mark.usefixtures("setup_entry")
@pytest.mark.parametrize(
    ("service_data", "expected_speak_kwargs"),
    [
        pytest.param({}, ENTITY_SPEAK_KWARGS, id="entry_options"),
        pytest.param(
            {
                tts.ATTR_LANGUAGE: "de-de",
                tts.ATTR_OPTIONS: {"gender": "Male", "type": "ConradNeural"},
            },
            ENTITY_SPEAK_KWARGS
            | {"language": "de-de", "gender": "Male", "voiceType": "ConradNeural"},
            id="service_options",
        ),
    ],
)
async def test_tts_speak(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    service_calls: list[ServiceCall],
    mock_tts_translator: MagicMock,
    service_data: dict[str, Any],
    expected_speak_kwargs: dict[str, Any],
) -> None:
    """Test the tts.speak action with the entity."""
    await hass.services.async_call(
        tts.DOMAIN,
        "speak",
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            tts.ATTR_MEDIA_PLAYER_ENTITY_ID: MEDIA_PLAYER_ENTITY_ID,
            tts.ATTR_MESSAGE: MESSAGE,
            **service_data,
        },
        blocking=True,
    )

    assert len(service_calls) == 2
    assert (
        await retrieve_media(
            hass, hass_client, service_calls[1].data[ATTR_MEDIA_CONTENT_ID]
        )
        == HTTPStatus.OK
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    mock_tts_translator.assert_called_with("test-api-key", "westeurope")
    mock_tts_translator.return_value.speak.assert_called_once_with(
        **expected_speak_kwargs
    )


@pytest.mark.usefixtures("setup_entry")
@pytest.mark.parametrize(
    (
        "translator_side_effect",
        "speak_side_effect",
        "speak_return_value",
        "translation_key",
    ),
    [
        pytest.param(
            http_error(HTTPStatus.UNAUTHORIZED),
            None,
            b"audio",
            "invalid_api_key",
            id="token_unauthorized",
        ),
        pytest.param(
            RequestsConnectionError, None, b"audio", "cannot_connect", id="token_error"
        ),
        pytest.param(None, HTTPError, b"audio", "cannot_connect", id="speak_error"),
        pytest.param(None, None, None, "synthesis_failed", id="speak_failed"),
    ],
)
async def test_tts_speak_error(
    hass: HomeAssistant,
    mock_tts_translator: MagicMock,
    translator_side_effect: Exception | type[Exception] | None,
    speak_side_effect: type[Exception] | None,
    speak_return_value: bytes | None,
    translation_key: str,
) -> None:
    """Test the entity raises an error if the speech synthesis fails."""
    mock_tts_translator.side_effect = translator_side_effect
    mock_tts_translator.return_value.speak.side_effect = speak_side_effect
    mock_tts_translator.return_value.speak.return_value = speak_return_value

    stream = tts.async_create_stream(hass, ENTITY_ID)
    stream.async_set_message(MESSAGE)

    with pytest.raises(HomeAssistantError) as exc_info:
        b"".join([chunk async for chunk in stream.async_stream_result()])

    assert exc_info.value.translation_key == translation_key


@pytest.mark.usefixtures("mock_tts_translator")
async def test_yaml_import(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the YAML configuration is imported and the legacy action is kept."""
    await setup_legacy_platform(hass, {})

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert hass.states.get(ENTITY_ID)
    assert hass.services.has_service(tts.DOMAIN, "microsoft_say")
    assert issue_registry.async_get_issue(DOMAIN, "deprecated_yaml") == snapshot


@pytest.mark.usefixtures("mock_tts_translator")
async def test_yaml_import_already_configured(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the YAML configuration is not imported twice."""
    mock_config_entry.add_to_hass(hass)

    await setup_legacy_platform(hass, {})

    assert hass.config_entries.async_entries(DOMAIN) == [mock_config_entry]
    assert hass.services.has_service(tts.DOMAIN, "microsoft_say")
    assert issue_registry.async_get_issue(DOMAIN, "deprecated_yaml")


@pytest.mark.parametrize(
    ("side_effect", "issue_id"),
    [
        pytest.param(
            http_error(HTTPStatus.UNAUTHORIZED),
            "deprecated_yaml_import_issue_invalid_api_key",
            id="invalid_api_key",
        ),
        pytest.param(
            RequestsConnectionError,
            "deprecated_yaml_import_issue_cannot_connect",
            id="cannot_connect",
        ),
        pytest.param(ValueError, "deprecated_yaml_import_issue_unknown", id="unknown"),
    ],
)
async def test_yaml_import_failed(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    issue_registry: ir.IssueRegistry,
    mock_tts_translator: MagicMock,
    side_effect: Exception,
    issue_id: str,
) -> None:
    """Test a failed import creates an issue."""
    mock_tts_translator.side_effect = side_effect

    await setup_legacy_platform(hass, {})

    assert not hass.config_entries.async_entries(DOMAIN)
    assert hass.services.has_service(tts.DOMAIN, "microsoft_say")
    assert issue_registry.async_get_issue(DOMAIN, issue_id) == snapshot


@pytest.mark.parametrize(
    (
        "config",
        "service_data",
        "speak_side_effect",
        "expected_status",
        "expected_speak_kwargs",
    ),
    [
        pytest.param({}, {}, None, HTTPStatus.OK, LEGACY_SPEAK_KWARGS, id="defaults"),
        pytest.param(
            {"language": "en-gb", "type": "AbbiNeural"},
            {},
            None,
            HTTPStatus.OK,
            LEGACY_SPEAK_KWARGS | {"language": "en-gb", "voiceType": "AbbiNeural"},
            id="en_gb_config",
        ),
        pytest.param(
            {},
            {tts.ATTR_LANGUAGE: "en-gb", tts.ATTR_OPTIONS: {"type": "AbbiNeural"}},
            None,
            HTTPStatus.OK,
            LEGACY_SPEAK_KWARGS | {"language": "en-gb", "voiceType": "AbbiNeural"},
            id="en_gb_service",
        ),
        pytest.param(
            {"language": "fa-ir", "type": "DilaraNeural"},
            {},
            None,
            HTTPStatus.OK,
            LEGACY_SPEAK_KWARGS | {"language": "fa-ir", "voiceType": "DilaraNeural"},
            id="fa_ir_config",
        ),
        pytest.param(
            {"service_name": "microsoft_say"},
            {tts.ATTR_LANGUAGE: "fa-ir", tts.ATTR_OPTIONS: {"type": "DilaraNeural"}},
            None,
            HTTPStatus.OK,
            LEGACY_SPEAK_KWARGS | {"language": "fa-ir", "voiceType": "DilaraNeural"},
            id="fa_ir_service",
        ),
        pytest.param(
            {},
            {},
            HTTPError,
            HTTPStatus.INTERNAL_SERVER_ERROR,
            LEGACY_SPEAK_KWARGS,
            id="http_error",
        ),
    ],
)
async def test_legacy_service_say(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_tts_translator: MagicMock,
    service_calls: list[ServiceCall],
    config: dict[str, Any],
    service_data: dict[str, Any],
    speak_side_effect: type[Exception] | None,
    expected_status: HTTPStatus,
    expected_speak_kwargs: dict[str, Any],
) -> None:
    """Test the legacy say action."""
    mock_tts_translator.return_value.speak.side_effect = speak_side_effect
    await setup_legacy_platform(hass, config)

    await hass.services.async_call(
        tts.DOMAIN,
        "microsoft_say",
        {
            ATTR_ENTITY_ID: MEDIA_PLAYER_ENTITY_ID,
            tts.ATTR_MESSAGE: MESSAGE,
            **service_data,
        },
        blocking=True,
    )

    assert len(service_calls) == 2
    assert (
        await retrieve_media(
            hass, hass_client, service_calls[1].data[ATTR_MEDIA_CONTENT_ID]
        )
        == expected_status
    )
    mock_tts_translator.return_value.speak.assert_called_once_with(
        **expected_speak_kwargs
    )


def test_supported_languages() -> None:
    """Test list of supported languages."""
    for lang in ("en-us", "fa-ir", "en-gb"):
        assert lang in SUPPORTED_LANGUAGES
    assert "en-US" not in SUPPORTED_LANGUAGES
    for lang in (
        "en",
        "en-uk",
        "english",
        "english (united states)",
        "jennyneural",
        "en-us-jennyneural",
    ):
        assert lang not in {s.lower() for s in SUPPORTED_LANGUAGES}
    assert len(SUPPORTED_LANGUAGES) > 100


async def test_legacy_invalid_language(
    hass: HomeAssistant, mock_tts_translator: MagicMock
) -> None:
    """Test the legacy platform is not set up with an invalid language."""
    await setup_legacy_platform(hass, {"language": "en"})

    with pytest.raises(ServiceNotFound):
        await hass.services.async_call(
            tts.DOMAIN,
            "microsoft_say",
            {ATTR_ENTITY_ID: MEDIA_PLAYER_ENTITY_ID, tts.ATTR_MESSAGE: MESSAGE},
            blocking=True,
        )

    assert len(mock_tts_translator.mock_calls) == 0
