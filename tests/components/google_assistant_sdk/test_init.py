"""Tests for Google Assistant SDK."""
from datetime import timedelta
import http
import time
from unittest.mock import call, patch

import aiohttp
import pytest

from homeassistant.components import conversation
from homeassistant.components.google_assistant_sdk import DOMAIN
from homeassistant.components.google_assistant_sdk.const import SUPPORTED_LANGUAGE_CODES
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import Context, HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util.dt import utcnow

from .conftest import ComponentSetup, ExpectedCredentials

from tests.common import MockConfigEntry, async_fire_time_changed, async_mock_service
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator


async def fetch_api_url(hass_client, url):
    """Fetch an API URL and return HTTP status and contents."""
    client = await hass_client()
    response = await client.get(url)
    contents = await response.read()
    return response.status, contents


async def test_setup_success(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
) -> None:
    """Test successful setup and unload."""
    await setup_integration()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(entries[0].entry_id)
    await hass.async_block_till_done()

    assert not hass.data.get(DOMAIN)
    assert entries[0].state is ConfigEntryState.NOT_LOADED
    assert not hass.services.async_services().get(DOMAIN, {})


@pytest.mark.parametrize("expires_at", [time.time() - 3600], ids=["expired"])
async def test_expired_token_refresh_success(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test expired token is refreshed."""

    aioclient_mock.post(
        "https://oauth2.googleapis.com/token",
        json={
            "access_token": "updated-access-token",
            "refresh_token": "updated-refresh-token",
            "expires_at": time.time() + 3600,
            "expires_in": 3600,
        },
    )

    await setup_integration()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.LOADED
    assert entries[0].data["token"]["access_token"] == "updated-access-token"
    assert entries[0].data["token"]["expires_in"] == 3600


@pytest.mark.parametrize(
    ("expires_at", "status", "expected_state"),
    [
        (
            time.time() - 3600,
            http.HTTPStatus.UNAUTHORIZED,
            ConfigEntryState.SETUP_ERROR,
        ),
        (
            time.time() - 3600,
            http.HTTPStatus.INTERNAL_SERVER_ERROR,
            ConfigEntryState.SETUP_RETRY,
        ),
    ],
    ids=["failure_requires_reauth", "transient_failure"],
)
async def test_expired_token_refresh_failure(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    aioclient_mock: AiohttpClientMocker,
    status: http.HTTPStatus,
    expected_state: ConfigEntryState,
) -> None:
    """Test failure while refreshing token with a transient error."""

    aioclient_mock.post(
        "https://oauth2.googleapis.com/token",
        status=status,
    )

    await setup_integration()

    # Verify a transient failure has occurred
    entries = hass.config_entries.async_entries(DOMAIN)
    assert entries[0].state is expected_state


@pytest.mark.parametrize(
    ("configured_language_code", "expected_language_code"),
    [("", "en-US"), ("en-US", "en-US"), ("es-ES", "es-ES")],
    ids=["default", "english", "spanish"],
)
async def test_send_text_command(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    configured_language_code: str,
    expected_language_code: str,
) -> None:
    """Test service call send_text_command calls TextAssistant."""
    await setup_integration()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.LOADED
    if configured_language_code:
        entries[0].options = {"language_code": configured_language_code}

    command = "turn on home assistant unsupported device"
    with patch(
        "homeassistant.components.google_assistant_sdk.helpers.TextAssistant"
    ) as mock_text_assistant:
        await hass.services.async_call(
            DOMAIN,
            "send_text_command",
            {"command": command},
            blocking=True,
        )
    mock_text_assistant.assert_called_once_with(
        ExpectedCredentials(), expected_language_code, audio_out=False
    )
    mock_text_assistant.assert_has_calls([call().__enter__().assist(command)])


async def test_send_text_commands(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
) -> None:
    """Test service call send_text_command calls TextAssistant."""
    await setup_integration()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.LOADED

    command1 = "open the garage door"
    command2 = "1234"
    command1_response = "what's the PIN?"
    command2_response = "opened the garage door"
    with patch(
        "homeassistant.components.google_assistant_sdk.helpers.TextAssistant.assist",
        side_effect=[
            (command1_response, None, None),
            (command2_response, None, None),
        ],
    ) as mock_assist_call:
        response = await hass.services.async_call(
            DOMAIN,
            "send_text_command",
            {"command": [command1, command2]},
            blocking=True,
            return_response=True,
        )
        assert response == {
            "responses": [{"text": command1_response}, {"text": command2_response}]
        }
    mock_assist_call.assert_has_calls([call(command1), call(command2)])


@pytest.mark.parametrize(
    ("status", "requires_reauth"),
    [
        (
            http.HTTPStatus.UNAUTHORIZED,
            True,
        ),
        (
            http.HTTPStatus.INTERNAL_SERVER_ERROR,
            False,
        ),
    ],
    ids=["failure_requires_reauth", "transient_failure"],
)
async def test_send_text_command_expired_token_refresh_failure(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    aioclient_mock: AiohttpClientMocker,
    status: http.HTTPStatus,
    requires_reauth: ConfigEntryState,
) -> None:
    """Test failure refreshing token in send_text_command."""
    await async_setup_component(hass, "homeassistant", {})
    await setup_integration()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    entry = entries[0]
    assert entry.state is ConfigEntryState.LOADED

    entry.data["token"]["expires_at"] = time.time() - 3600
    aioclient_mock.post(
        "https://oauth2.googleapis.com/token",
        status=status,
    )

    with pytest.raises(aiohttp.ClientResponseError):
        await hass.services.async_call(
            DOMAIN,
            "send_text_command",
            {"command": "turn on tv"},
            blocking=True,
        )
    await hass.async_block_till_done()

    assert any(entry.async_get_active_flows(hass, {"reauth"})) == requires_reauth


async def test_send_text_command_media_player(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test send_text_command with media_player."""
    await setup_integration()

    play_media_calls = async_mock_service(hass, "media_player", "play_media")

    command = "tell me a joke"
    media_player = "media_player.office_speaker"
    audio_response1 = b"joke1 audio response bytes"
    audio_response2 = b"joke2 audio response bytes"
    with patch(
        "homeassistant.components.google_assistant_sdk.helpers.TextAssistant.assist",
        side_effect=[
            ("joke1 text", None, audio_response1),
            ("joke2 text", None, audio_response2),
        ],
    ) as mock_assist_call:
        # Run the same command twice, getting different audio response each time.
        await hass.services.async_call(
            DOMAIN,
            "send_text_command",
            {
                "command": command,
                "media_player": media_player,
            },
            blocking=True,
        )
        await hass.services.async_call(
            DOMAIN,
            "send_text_command",
            {
                "command": command,
                "media_player": media_player,
            },
            blocking=True,
        )

    mock_assist_call.assert_has_calls([call(command), call(command)])
    assert len(play_media_calls) == 2
    for play_media_call in play_media_calls:
        assert play_media_call.data["entity_id"] == [media_player]
        assert play_media_call.data["media_content_id"].startswith(
            "/api/google_assistant_sdk/audio/"
        )

    audio_url1 = play_media_calls[0].data["media_content_id"]
    audio_url2 = play_media_calls[1].data["media_content_id"]
    assert audio_url1 != audio_url2

    # Assert that both audio responses can be served
    status, response = await fetch_api_url(hass_client, audio_url1)
    assert status == http.HTTPStatus.OK
    assert response == audio_response1
    status, response = await fetch_api_url(hass_client, audio_url2)
    assert status == http.HTTPStatus.OK
    assert response == audio_response2

    # Assert a nonexistent URL returns 404
    status, _ = await fetch_api_url(
        hass_client, "/api/google_assistant_sdk/audio/nonexistent"
    )
    assert status == http.HTTPStatus.NOT_FOUND

    # Assert that both audio responses can still be served before the 5 minutes expiration
    async_fire_time_changed(hass, utcnow() + timedelta(minutes=4))
    status, response = await fetch_api_url(hass_client, audio_url1)
    assert status == http.HTTPStatus.OK
    assert response == audio_response1
    status, response = await fetch_api_url(hass_client, audio_url2)
    assert status == http.HTTPStatus.OK
    assert response == audio_response2

    # Assert that they cannot be served after the 5 minutes expiration
    async_fire_time_changed(hass, utcnow() + timedelta(minutes=6))
    status, response = await fetch_api_url(hass_client, audio_url1)
    assert status == http.HTTPStatus.NOT_FOUND
    status, response = await fetch_api_url(hass_client, audio_url2)
    assert status == http.HTTPStatus.NOT_FOUND


async def test_conversation_agent(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    config_entry: MockConfigEntry,
) -> None:
    """Test GoogleAssistantConversationAgent."""
    await setup_integration()

    assert await async_setup_component(hass, "conversation", {})

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    entry = entries[0]
    assert entry.state is ConfigEntryState.LOADED

    agent = await conversation._get_agent_manager(hass).async_get_agent(entry.entry_id)
    assert agent.supported_languages == SUPPORTED_LANGUAGE_CODES

    text1 = "tell me a joke"
    text2 = "tell me another one"
    with patch(
        "homeassistant.components.google_assistant_sdk.TextAssistant"
    ) as mock_text_assistant:
        await conversation.async_converse(
            hass, text1, None, Context(), "en-US", config_entry.entry_id
        )
        await conversation.async_converse(
            hass, text2, None, Context(), "en-US", config_entry.entry_id
        )

    # Assert constructor is called only once since it's reused across requests
    assert mock_text_assistant.call_count == 1
    mock_text_assistant.assert_called_once_with(ExpectedCredentials(), "en-US")
    mock_text_assistant.assert_has_calls([call().assist(text1)])
    mock_text_assistant.assert_has_calls([call().assist(text2)])


async def test_conversation_agent_refresh_token(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    setup_integration: ComponentSetup,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test GoogleAssistantConversationAgent when token is expired."""
    await setup_integration()

    assert await async_setup_component(hass, "conversation", {})

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    entry = entries[0]
    assert entry.state is ConfigEntryState.LOADED

    text1 = "tell me a joke"
    text2 = "tell me another one"
    with patch(
        "homeassistant.components.google_assistant_sdk.TextAssistant"
    ) as mock_text_assistant:
        await conversation.async_converse(
            hass, text1, None, Context(), "en-US", config_entry.entry_id
        )

        # Expire the token between requests
        entry.data["token"]["expires_at"] = time.time() - 3600
        updated_access_token = "updated-access-token"
        aioclient_mock.post(
            "https://oauth2.googleapis.com/token",
            json={
                "access_token": updated_access_token,
                "refresh_token": "updated-refresh-token",
                "expires_at": time.time() + 3600,
                "expires_in": 3600,
            },
        )

        await conversation.async_converse(
            hass, text2, None, Context(), "en-US", config_entry.entry_id
        )

    # Assert constructor is called twice since the token was expired
    assert mock_text_assistant.call_count == 2
    mock_text_assistant.assert_has_calls([call(ExpectedCredentials(), "en-US")])
    mock_text_assistant.assert_has_calls(
        [call(ExpectedCredentials(updated_access_token), "en-US")]
    )
    mock_text_assistant.assert_has_calls([call().assist(text1)])
    mock_text_assistant.assert_has_calls([call().assist(text2)])


async def test_conversation_agent_language_changed(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    setup_integration: ComponentSetup,
) -> None:
    """Test GoogleAssistantConversationAgent when language is changed."""
    await setup_integration()

    assert await async_setup_component(hass, "conversation", {})

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    entry = entries[0]
    assert entry.state is ConfigEntryState.LOADED

    text1 = "tell me a joke"
    text2 = "cuéntame un chiste"
    with patch(
        "homeassistant.components.google_assistant_sdk.TextAssistant"
    ) as mock_text_assistant:
        await conversation.async_converse(
            hass, text1, None, Context(), "en-US", config_entry.entry_id
        )
        await conversation.async_converse(
            hass, text2, None, Context(), "es-ES", config_entry.entry_id
        )

    # Assert constructor is called twice since the language was changed
    assert mock_text_assistant.call_count == 2
    mock_text_assistant.assert_has_calls([call(ExpectedCredentials(), "en-US")])
    mock_text_assistant.assert_has_calls([call(ExpectedCredentials(), "es-ES")])
    mock_text_assistant.assert_has_calls([call().assist(text1)])
    mock_text_assistant.assert_has_calls([call().assist(text2)])
