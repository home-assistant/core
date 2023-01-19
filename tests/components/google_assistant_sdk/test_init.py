"""Tests for Google Assistant SDK."""
import http
import time
from unittest.mock import call, patch

import aiohttp
import pytest

from homeassistant.components.google_assistant_sdk import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .conftest import ComponentSetup, ExpectedCredentials

from tests.test_util.aiohttp import AiohttpClientMocker


async def test_setup_success(
    hass: HomeAssistant, setup_integration: ComponentSetup
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
    "expires_at,status,expected_state",
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
    "configured_language_code,expected_language_code",
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
        ExpectedCredentials(), expected_language_code
    )
    mock_text_assistant.assert_has_calls([call().__enter__().assist(command)])


@pytest.mark.parametrize(
    "status,requires_reauth",
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

    assert any(entry.async_get_active_flows(hass, {"reauth"})) == requires_reauth


async def test_conversation_agent(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
) -> None:
    """Test GoogleAssistantConversationAgent."""
    await setup_integration()

    assert await async_setup_component(hass, "conversation", {})

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    entry = entries[0]
    assert entry.state is ConfigEntryState.LOADED
    hass.config_entries.async_update_entry(
        entry, options={"enable_conversation_agent": True}
    )
    await hass.async_block_till_done()

    text1 = "tell me a joke"
    text2 = "tell me another one"
    with patch(
        "homeassistant.components.google_assistant_sdk.TextAssistant"
    ) as mock_text_assistant:
        await hass.services.async_call(
            "conversation",
            "process",
            {"text": text1},
            blocking=True,
        )
        await hass.services.async_call(
            "conversation",
            "process",
            {"text": text2},
            blocking=True,
        )

    # Assert constructor is called only once since it's reused across requests
    assert mock_text_assistant.call_count == 1
    mock_text_assistant.assert_called_once_with(ExpectedCredentials(), "en-US")
    mock_text_assistant.assert_has_calls([call().assist(text1)])
    mock_text_assistant.assert_has_calls([call().assist(text2)])


async def test_conversation_agent_refresh_token(
    hass: HomeAssistant,
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
    hass.config_entries.async_update_entry(
        entry, options={"enable_conversation_agent": True}
    )
    await hass.async_block_till_done()

    text1 = "tell me a joke"
    text2 = "tell me another one"
    with patch(
        "homeassistant.components.google_assistant_sdk.TextAssistant"
    ) as mock_text_assistant:
        await hass.services.async_call(
            "conversation",
            "process",
            {"text": text1},
            blocking=True,
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

        await hass.services.async_call(
            "conversation",
            "process",
            {"text": text2},
            blocking=True,
        )

    # Assert constructor is called twice since the token was expired
    assert mock_text_assistant.call_count == 2
    mock_text_assistant.assert_has_calls([call(ExpectedCredentials(), "en-US")])
    mock_text_assistant.assert_has_calls(
        [call(ExpectedCredentials(updated_access_token), "en-US")]
    )
    mock_text_assistant.assert_has_calls([call().assist(text1)])
    mock_text_assistant.assert_has_calls([call().assist(text2)])
