"""Test conversation."""

from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion
from wyoming.asr import Transcript
from wyoming.handle import Handled, NotHandled
from wyoming.info import Info
from wyoming.intent import Entity, Intent, IntentsStart, IntentsStop, NotRecognized

from homeassistant.components import conversation
from homeassistant.components.conversation import chat_log
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import MATCH_ALL
from homeassistant.core import Context, HomeAssistant, State
from homeassistant.helpers import intent

from . import HANDLE_INFO, INTENT_INFO, MockAsyncTcpClient

from tests.components.conversation import MockChatLog, mock_chat_log  # noqa: F401


async def test_intent(
    hass: HomeAssistant,
    init_wyoming_intent: ConfigEntry,
    mock_chat_log: MockChatLog,  # noqa: F811
) -> None:
    """Test when an intent is recognized."""
    agent_id = "conversation.test_intent"
    conversation_id = mock_chat_log.conversation_id
    satellite_id = "satellite-1234"
    device_id = "device-1234"

    test_intent = Intent(
        name="TestIntent",
        entities=[Entity(name="entity", value="value")],
        text="""
        {# Verify template variables are present #}
        {% if slots.entity == 'value' %}
        {% if slots.slot_name == 'slot_value' %}
        {% if state.entity_id == 'test.matched1' %}
        {% if query.matched[0].entity_id == 'test.matched1' %}
        {% if query.unmatched[0].entity_id == 'test.unmatched1' %}
        {% if query.unmatched[1].entity_id == 'test.unmatched2' %}
        success
        {% endif %}
        {% endif %}
        {% endif %}
        {% endif %}
        {% endif %}
        {% endif %}
        """,
    )

    class TestIntentHandler(intent.IntentHandler):
        """Test Intent Handler."""

        intent_type = "TestIntent"

        async def async_handle(self, intent_obj: intent.Intent):
            """Handle the intent."""
            assert intent_obj.slots.get("entity", {}).get("value") == "value"
            assert intent_obj.satellite_id == satellite_id
            assert intent_obj.device_id == device_id
            response = intent_obj.create_response()

            # Add parts to test response rendering
            response.async_set_speech_slots({"slot_name": "slot_value"})
            response.async_set_states(
                matched_states=[State("test.matched1", "on")],
                unmatched_states=[
                    State("test.unmatched1", "off"),
                    State("test.unmatched2", "off"),
                ],
            )

            return response

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
        "device_id": device_id,
    }

    assert result.response.response_type is intent.IntentResponseType.ACTION_DONE
    assert result.response.speech, "No speech"
    assert result.response.speech.get("plain", {}).get("speech") == "success"
    assert result.conversation_id == conversation_id

    # Verify that chat log recorded intent as tool call
    content: chat_log.AssistantContent | None = next(
        filter(
            lambda c: isinstance(c, chat_log.AssistantContent), mock_chat_log.content
        ),
        None,
    )
    assert content is not None, "Missing assistant content"
    assert content.tool_calls and len(content.tool_calls) == 1
    tool_call = content.tool_calls[0]
    assert tool_call.tool_name == test_intent.name
    assert tool_call.tool_args == {
        e.name: {"value": e.value} for e in test_intent.entities
    }


async def test_multiple_intents(
    hass: HomeAssistant,
    init_wyoming_intent: ConfigEntry,
    mock_chat_log: MockChatLog,  # noqa: F811
) -> None:
    """Test when more than one intent is recognized."""
    agent_id = "conversation.test_intent"
    conversation_id = mock_chat_log.conversation_id
    satellite_id = "satellite-1234"
    device_id = "device-1234"

    test_intent1 = Intent(
        name="TestIntent1",
        entities=[Entity(name="entity1", value="value1")],
        text="{{ slots.slot_name }}",
    )

    test_intent2 = Intent(
        name="TestIntent2",
        entities=[Entity(name="entity2", value="value2")],
        text="{{ slots.slot_name }}",
    )

    class TestIntentHandler(intent.IntentHandler):
        """Test Intent Handler."""

        def __init__(self, intent_type: str, slot_value: str) -> None:
            """Initialize the handler."""
            self.intent_type = intent_type
            self._slot_value = slot_value

        async def async_handle(self, intent_obj: intent.Intent):
            """Handle the intent."""
            response = intent_obj.create_response()
            response.async_set_speech_slots({"slot_name": self._slot_value})
            return response

    intent.async_register(hass, TestIntentHandler("TestIntent1", "slot value 1"))
    intent.async_register(hass, TestIntentHandler("TestIntent2", "slot value 2"))

    # Send multiple intent events framed by intents-start and intents-stop.
    client = MockAsyncTcpClient(
        [
            IntentsStart().event(),
            test_intent1.event(),
            test_intent2.event(),
            IntentsStop().event(),
        ]
    )
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

    assert result.response.response_type is intent.IntentResponseType.ACTION_DONE
    assert result.response.speech, "No speech"

    # Speech results are joined with newlines because punctuation would be
    # language-dependent.
    assert (
        result.response.speech.get("plain", {}).get("speech")
        == "slot value 1\nslot value 2"
    )

    # Verify that chat log recorded all intents as tool calls
    content: chat_log.AssistantContent | None = next(
        filter(
            lambda c: isinstance(c, chat_log.AssistantContent), mock_chat_log.content
        ),
        None,
    )
    assert content is not None, "Missing assistant content"
    assert content.tool_calls and len(content.tool_calls) == 2

    for tool_call, test_intent in zip(
        content.tool_calls, (test_intent1, test_intent2), strict=True
    ):
        assert tool_call.tool_name == test_intent.name
        assert tool_call.tool_args == {
            e.name: {"value": e.value} for e in test_intent.entities
        }


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

    assert result.response.response_type is intent.IntentResponseType.ERROR
    assert result.response.error_code == intent.IntentResponseErrorCode.FAILED_TO_HANDLE


async def test_multiple_intents_handle_error(
    hass: HomeAssistant,
    init_wyoming_intent: ConfigEntry,
    mock_chat_log: MockChatLog,  # noqa: F811
) -> None:
    """Test error during handling when multiple intents are recognized."""
    agent_id = "conversation.test_intent"

    test_intent_1 = Intent(name="TestIntent1", entities=[], text="success")
    test_intent_2 = Intent(name="TestIntent2", entities=[], text="success")

    class TestIntentHandler1(intent.IntentHandler):
        """Test Intent Handler."""

        intent_type = "TestIntent1"

        async def async_handle(self, intent_obj: intent.Intent):
            """Handle the intent."""
            return intent_obj.create_response()

    class TestIntentHandler2(intent.IntentHandler):
        """Test Intent Handler."""

        intent_type = "TestIntent2"

        async def async_handle(self, intent_obj: intent.Intent):
            """Handle the intent."""
            raise intent.IntentError

    intent.async_register(hass, TestIntentHandler1())
    intent.async_register(hass, TestIntentHandler2())

    with patch(
        "homeassistant.components.wyoming.conversation.AsyncTcpClient",
        MockAsyncTcpClient(
            [
                IntentsStart().event(),
                test_intent_1.event(),
                test_intent_2.event(),
                IntentsStop().event(),
            ]
        ),
    ):
        result = await conversation.async_converse(
            hass=hass,
            text="test text",
            conversation_id=None,
            context=Context(),
            language=hass.config.language,
            agent_id=agent_id,
        )

    assert result.response.response_type is intent.IntentResponseType.ERROR
    assert result.response.error_code == intent.IntentResponseErrorCode.FAILED_TO_HANDLE

    # Ensure that no tool calls were recorded
    assert not any(
        isinstance(c, chat_log.AssistantContent) for c in mock_chat_log.content
    )


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

    assert result.response.response_type is intent.IntentResponseType.ERROR
    assert result.response.error_code == intent.IntentResponseErrorCode.NO_INTENT_MATCH
    assert result.response.speech, "No speech"
    assert result.response.speech.get("plain", {}).get("speech") == "failure"


async def test_handle(hass: HomeAssistant, init_wyoming_handle: ConfigEntry) -> None:
    """Test when an intent is handled."""
    agent_id = "conversation.test_handle"
    conversation_id = "conversation-1234"
    satellite_id = "satellite-1234"
    device_id = "device-1234"

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
            device_id=device_id,
        )

    # Ensure language and context are sent
    assert client.transcript is not None
    assert client.transcript.language == hass.config.language
    assert client.transcript.context == {
        "conversation_id": conversation_id,
        "satellite_id": satellite_id,
        "device_id": device_id,
    }

    assert result.response.response_type is intent.IntentResponseType.ACTION_DONE
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

    assert result.response.response_type is intent.IntentResponseType.ERROR
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

    assert result.response.response_type is intent.IntentResponseType.ERROR
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

    assert result.response.response_type is intent.IntentResponseType.ERROR
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
    """Test empty supported languages means agent supports all."""
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


async def test_intent_supports_home_control(
    hass: HomeAssistant, intent_config_entry: ConfigEntry
) -> None:
    """Test that the CONTROL supported feature is always set for intent services."""
    agent_id = "conversation.test_intent"

    with patch(
        "homeassistant.components.wyoming.data.load_wyoming_info",
        return_value=Info(intent=INTENT_INFO.intent),
    ):
        await hass.config_entries.async_setup(intent_config_entry.entry_id)

    agent = conversation.async_get_agent(hass, agent_id)
    assert isinstance(agent, conversation.ConversationEntity)
    assert agent.supported_features is not None
    assert (
        agent.supported_features & conversation.ConversationEntityFeature.CONTROL
    ) == conversation.ConversationEntityFeature.CONTROL


@pytest.mark.parametrize(
    "supports_home_control",
    [False, True],
)
async def test_handle_supports_home_control(
    hass: HomeAssistant, intent_config_entry: ConfigEntry, supports_home_control: bool
) -> None:
    """Test that the CONTROL supported feature matches the Wyoming info."""
    agent_id = "conversation.test_handle"

    with (
        patch.object(
            HANDLE_INFO.handle[0], "supports_home_control", supports_home_control
        ),
        patch(
            "homeassistant.components.wyoming.data.load_wyoming_info",
            return_value=Info(handle=HANDLE_INFO.handle),
        ),
    ):
        await hass.config_entries.async_setup(intent_config_entry.entry_id)

    agent = conversation.async_get_agent(hass, agent_id)
    assert isinstance(agent, conversation.ConversationEntity)
    supported_features = (
        agent.supported_features or conversation.ConversationEntityFeature(0)
    )

    control_feature = (
        supported_features & conversation.ConversationEntityFeature.CONTROL
    )

    if supports_home_control:
        assert control_feature == conversation.ConversationEntityFeature.CONTROL
    else:
        assert control_feature == conversation.ConversationEntityFeature(0)
