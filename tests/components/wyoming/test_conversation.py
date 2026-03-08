"""Test conversation."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion
from wyoming.asr import Transcript
from wyoming.handle import Handled, NotHandled
from wyoming.info import Info
from wyoming.intent import Entity, Intent, NotRecognized

from homeassistant.components import conversation
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import MATCH_ALL
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import intent

from . import HANDLE_INFO, INTENT_INFO, MockAsyncTcpClient


async def test_intent(hass: HomeAssistant, init_wyoming_intent: ConfigEntry) -> None:
    """Test when an intent is recognized."""
    agent_id = "conversation.test_intent"
    conversation_id = "conversation-1234"
    satellite_id = "satellite-1234"
    device_id = "device-1234"

    test_intent = Intent(
        name="TestIntent",
        entities=[Entity(name="entity", value="value")],
        text="success",
    )

    class TestIntentHandler(intent.IntentHandler):
        """Test Intent Handler."""

        intent_type = "TestIntent"

        async def async_handle(self, intent_obj: intent.Intent):
            """Handle the intent."""
            assert intent_obj.slots.get("entity", {}).get("value") == "value"
            assert intent_obj.satellite_id == satellite_id
            assert intent_obj.device_id == device_id
            return intent_obj.create_response()

    intent.async_register(hass, TestIntentHandler())

    client = MockAsyncTcpClient([test_intent.event()])
    with patch(
        "homeassistant.components.wyoming.conversation.AsyncTcpClient",
        client,
    ):
        result = await conversation.async_converse(
            hass=hass,
            text="test text",
            conversation_id=conversation_id,
            context=Context(),
            language=hass.config.language,
            agent_id=agent_id,
            satellite_id=satellite_id,
            device_id=device_id,
        )

    # Ensure language and context are sent
    assert client.transcript is not None
    assert client.transcript.language == hass.config.language
    assert client.transcript.context == {
        "conversation_id": conversation_id,
        "satellite_id": satellite_id,
    }

    assert result.response.response_type == intent.IntentResponseType.ACTION_DONE
    assert result.response.speech, "No speech"
    assert result.response.speech.get("plain", {}).get("speech") == "success"
    assert result.conversation_id == conversation_id


async def test_intent_handle_error(
    hass: HomeAssistant, init_wyoming_intent: ConfigEntry
) -> None:
    """Test error during handling when an intent is recognized."""
    agent_id = "conversation.test_intent"

    test_intent = Intent(name="TestIntent", entities=[], text="success")

    class TestIntentHandler(intent.IntentHandler):
        """Test Intent Handler."""

        intent_type = "TestIntent"

        async def async_handle(self, intent_obj: intent.Intent):
            """Handle the intent."""
            raise intent.IntentError

    intent.async_register(hass, TestIntentHandler())

    with patch(
        "homeassistant.components.wyoming.conversation.AsyncTcpClient",
        MockAsyncTcpClient([test_intent.event()]),
    ):
        result = await conversation.async_converse(
            hass=hass,
            text="test text",
            conversation_id=None,
            context=Context(),
            language=hass.config.language,
            agent_id=agent_id,
        )

    assert result.response.response_type == intent.IntentResponseType.ERROR
    assert result.response.error_code == intent.IntentResponseErrorCode.FAILED_TO_HANDLE


async def test_not_recognized(
    hass: HomeAssistant, init_wyoming_intent: ConfigEntry
) -> None:
    """Test when an intent is not recognized."""
    agent_id = "conversation.test_intent"

    with patch(
        "homeassistant.components.wyoming.conversation.AsyncTcpClient",
        MockAsyncTcpClient([NotRecognized(text="failure").event()]),
    ):
        result = await conversation.async_converse(
            hass=hass,
            text="test text",
            conversation_id=None,
            context=Context(),
            language=hass.config.language,
            agent_id=agent_id,
        )

    assert result.response.response_type == intent.IntentResponseType.ERROR
    assert result.response.error_code == intent.IntentResponseErrorCode.NO_INTENT_MATCH
    assert result.response.speech, "No speech"
    assert result.response.speech.get("plain", {}).get("speech") == "failure"


async def test_handle(hass: HomeAssistant, init_wyoming_handle: ConfigEntry) -> None:
    """Test when an intent is handled."""
    agent_id = "conversation.test_handle"
    conversation_id = "conversation-1234"
    satellite_id = "satellite-1234"

    client = MockAsyncTcpClient([Handled(text="success").event()])
    with patch(
        "homeassistant.components.wyoming.conversation.AsyncTcpClient",
        client,
    ):
        result = await conversation.async_converse(
            hass=hass,
            text="test text",
            conversation_id=conversation_id,
            context=Context(),
            language=hass.config.language,
            agent_id=agent_id,
            satellite_id=satellite_id,
        )

    # Ensure language and context are sent
    assert client.transcript is not None
    assert client.transcript.language == hass.config.language
    assert client.transcript.context == {
        "conversation_id": conversation_id,
        "satellite_id": satellite_id,
    }

    assert result.response.response_type == intent.IntentResponseType.ACTION_DONE
    assert result.response.speech, "No speech"
    assert result.response.speech.get("plain", {}).get("speech") == "success"
    assert result.conversation_id == conversation_id


async def test_not_handled(
    hass: HomeAssistant, init_wyoming_handle: ConfigEntry
) -> None:
    """Test when an intent is not handled."""
    agent_id = "conversation.test_handle"

    with patch(
        "homeassistant.components.wyoming.conversation.AsyncTcpClient",
        MockAsyncTcpClient([NotHandled(text="failure").event()]),
    ):
        result = await conversation.async_converse(
            hass=hass,
            text="test text",
            conversation_id=None,
            context=Context(),
            language=hass.config.language,
            agent_id=agent_id,
        )

    assert result.response.response_type == intent.IntentResponseType.ERROR
    assert result.response.error_code == intent.IntentResponseErrorCode.FAILED_TO_HANDLE
    assert result.response.speech, "No speech"
    assert result.response.speech.get("plain", {}).get("speech") == "failure"


async def test_connection_lost(
    hass: HomeAssistant, init_wyoming_handle: ConfigEntry, snapshot: SnapshotAssertion
) -> None:
    """Test connection to client is lost."""
    agent_id = "conversation.test_handle"

    with patch(
        "homeassistant.components.wyoming.conversation.AsyncTcpClient",
        MockAsyncTcpClient([None]),
    ):
        result = await conversation.async_converse(
            hass=hass,
            text="test text",
            conversation_id=None,
            context=Context(),
            language=hass.config.language,
            agent_id=agent_id,
        )

    assert result.response.response_type == intent.IntentResponseType.ERROR
    assert result.response.error_code == intent.IntentResponseErrorCode.UNKNOWN
    assert result.response.speech, "No speech"
    assert result.response.speech.get("plain", {}).get("speech") == snapshot


async def test_oserror(
    hass: HomeAssistant, init_wyoming_handle: ConfigEntry, snapshot: SnapshotAssertion
) -> None:
    """Test connection error."""
    agent_id = "conversation.test_handle"

    mock_client = MockAsyncTcpClient([Transcript("success").event()])

    with (
        patch(
            "homeassistant.components.wyoming.conversation.AsyncTcpClient", mock_client
        ),
        patch.object(mock_client, "read_event", side_effect=OSError("Boom!")),
    ):
        result = await conversation.async_converse(
            hass=hass,
            text="test text",
            conversation_id=None,
            context=Context(),
            language=hass.config.language,
            agent_id=agent_id,
        )

    assert result.response.response_type == intent.IntentResponseType.ERROR
    assert result.response.error_code == intent.IntentResponseErrorCode.UNKNOWN
    assert result.response.speech, "No speech"
    assert result.response.speech.get("plain", {}).get("speech") == snapshot


@pytest.mark.parametrize(
    ("config_entry_fixture", "info_obj", "info_kwargs", "agent_id"),
    [
        (
            "intent_config_entry",
            INTENT_INFO.intent[0].models[0],
            {"intent": INTENT_INFO.intent},
            "conversation.test_intent",
        ),
        (
            "handle_config_entry",
            HANDLE_INFO.handle[0].models[0],
            {"handle": HANDLE_INFO.handle},
            "conversation.test_handle",
        ),
    ],
)
async def test_supported_languages_empty_means_all(
    hass: HomeAssistant,
    request: pytest.FixtureRequest,
    config_entry_fixture: str,
    info_obj,
    info_kwargs: dict,
    agent_id: str,
) -> None:
    """Test that an empty list of supported languages means the agent supports all languages."""
    config_entry: ConfigEntry = request.getfixturevalue(config_entry_fixture)

    with (
        patch.object(info_obj, "languages", []),
        patch(
            "homeassistant.components.wyoming.data.load_wyoming_info",
            return_value=Info(**info_kwargs),
        ),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)

    agent = conversation.async_get_agent(hass, agent_id)
    assert agent is not None
    assert agent.supported_languages == MATCH_ALL
