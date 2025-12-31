"""Tests for the Google Generative AI Conversation integration with Thinking models using a Fake Chat."""

from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, patch

from google.genai.errors import ClientError
from google.genai.types import Content, FunctionCall, GenerateContentResponse, Part
import pytest

from homeassistant.components import conversation
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import intent

from tests.common import MockConfigEntry
from tests.components.conversation import (
    MockChatLog,
    mock_chat_log,  # noqa: F401
)


class FakeAsyncChat:
    """A fake AsyncChat that allows setting a custom history."""

    def __init__(self, history=None):
        """Initialize the fake chat with a history."""
        self.history = history or []

    @property
    def get_history(self):
        """Return the current history."""
        return self.history

    @property
    def _curated_history(self):
        return self.history

    async def send_message_stream(
        self, message
    ) -> AsyncIterator[GenerateContentResponse]:
        """Simulate sending a message and receiving a streamed response."""
        # message is what the user/tool sends.
        # Add it to history.
        # Check constraints before proceeding.

        # In the real SDK, the user message is added to history.
        # message is list of PartUnionDict or similar.
        # For simplicity, we just look at the last Turn in history to simulate the server check.

        # Check if the previous turn was a function call turn that ended with non-empty text
        if self.history:
            last_msg = self.history[-1]
            if last_msg.role == "model":
                has_func_call = any(
                    p.function_call for p in last_msg.parts if p.function_call
                )
                has_trailing_empty_text = (
                    last_msg.parts and last_msg.parts[-1].text == ""
                )

                # This simulates the API 400 error condition
                if has_func_call and has_trailing_empty_text:
                    # If we are here, it means the client (HA) tried to send a response (this call),
                    # but the history currently on the server (simulated here) is invalid.
                    raise ClientError(
                        code=400,
                        response_json={
                            "error": {
                                "message": "Please ensure that function response turn comes immediately after a function call turn.",
                                "status": "INVALID_ARGUMENT",
                            }
                        },
                    )

        # Simulate response generation
        # Scenario: User sends "Do thing" -> Model returns [Call, EmptyText]
        # Scenario: User sends ToolResult -> Model returns "Done"

        # We need to distinguish turns based on input or state.
        # Simple finite state machine for this test.

        response_candidates = []

        # If history is just User message (first turn)
        if not self.history:
            # This is the "Do the thing" turn
            # Response: Call + Empty Text
            response_candidates = [
                {
                    "content": {
                        "parts": [
                            {
                                "function_call": {
                                    "name": "test_tool",
                                    "args": {"param1": "test"},
                                },
                            },
                            {
                                "text": "",  # The poison!
                            },
                        ],
                        "role": "model",
                    }
                }
            ]
        else:
            # Assume it's the tool response turn
            response_candidates = [
                {
                    "content": {
                        "parts": [{"text": "Done!"}],
                        "role": "model",
                    },
                    "finish_reason": "STOP",
                }
            ]

        # In real SDK, the SDK appends the generated response to history
        current_response_parts = []
        for cand in response_candidates:
            for p in cand["content"]["parts"]:
                if "function_call" in p:
                    current_response_parts.append(
                        Part(function_call=FunctionCall(**p["function_call"]))
                    )
                elif "text" in p:
                    current_response_parts.append(Part(text=p["text"]))

        self.history.append(Content(role="model", parts=current_response_parts))

        async def generator():
            for cand in response_candidates:
                # We need to wrap it into a GenerateContentResponse
                # Note: The real SDK yields chunks, but for our logic, yielding one response is fine
                # as long as _transform_stream handles it.
                # However, _transform_stream needs proper structure.

                # Hack: construct a minimal object that mimics what _transform_stream expects
                # It expects response.candidates[0].content.parts

                # We can use the actual types if available, or mocks.
                # Let's try to preserve the dictionary structure but accessable as attributes?
                # No, usage in entity.py implies attributes.

                # We'll rely on the fact that we can mock the response object yielded
                yield _create_mock_response(cand)

        return generator()


def _create_mock_response(cand_dict):
    # Create a mock object that mimics GenerateContentResponse structure
    cand = AsyncMock()
    cand.finish_reason = cand_dict.get("finish_reason")

    parts = []
    for p in cand_dict["content"]["parts"]:
        part = AsyncMock()
        part.text = p.get("text")
        part.thought = False
        part.thought_signature = None
        part.function_call = None
        if "function_call" in p:
            fc = AsyncMock()
            fc.name = p["function_call"]["name"]
            fc.args = p["function_call"]["args"]
            part.function_call = fc
        parts.append(part)

    cand.content.parts = parts

    resp = AsyncMock()
    resp.candidates = [cand]
    resp.prompt_feedback = None
    return resp


@pytest.fixture(autouse=True)
def mock_ulid_tools():
    """Mock generated ULIDs for tool calls."""
    with patch("homeassistant.helpers.llm.ulid_now", return_value="mock-tool-call"):
        yield


@pytest.mark.usefixtures("mock_init_component")
@pytest.mark.usefixtures("mock_ulid_tools")
async def test_thinking_model_crash_repro(
    hass: HomeAssistant,
    mock_config_entry_with_assist: MockConfigEntry,
    mock_chat_log: MockChatLog,  # noqa: F811
) -> None:
    """Test reproduction of the 400 error using FakeAsyncChat."""
    agent_id = "conversation.google_ai_conversation"
    context = Context()

    mock_chat_log.mock_tool_results(
        {
            "mock-tool-call": {"result": "Success"},
        }
    )

    # We mock the chats.create to return our FakeAsyncChat
    # We also need to capture what is passed to create to ensure history is passed?
    # Actually, FakeAsyncChat will maintain its own history after creation.

    def create_side_effect(model=None, history=None, config=None):
        return FakeAsyncChat(history=history)

    with patch("google.genai.chats.AsyncChats.create", side_effect=create_side_effect):
        # This should NO LONGER raise an exception because of the workaround in entity.py
        result = await conversation.async_converse(
            hass,
            "Do the thing",
            mock_chat_log.conversation_id,
            context,
            agent_id=agent_id,
            device_id="test_device",
        )

        # Verify action done
        assert result.response.response_type == intent.IntentResponseType.ACTION_DONE
        assert result.response.as_dict()["speech"]["plain"]["speech"] == "Done!"
