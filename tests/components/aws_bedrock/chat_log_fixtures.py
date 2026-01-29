"""Sample chat logs for testing _async_handle_chat_log method."""

from pathlib import Path

from homeassistant.components import conversation
from homeassistant.helpers import llm


def create_simple_user_message(
    message: str = "What's the weather like today?",
) -> list[conversation.Content]:
    """Create a simple user message without any tools or attachments."""
    return [
        conversation.UserContent(
            content=message,
        )
    ]


def create_message_with_system_prompt(
    system_prompt: str = "You are a helpful home automation assistant.",
    user_message: str = "Turn on the lights in the living room",
) -> list[conversation.Content]:
    """Create messages with a system prompt."""
    return [
        conversation.SystemContent(content=system_prompt),
        conversation.UserContent(
            content=user_message,
        ),
    ]


def create_conversation_history(
    turns: list[tuple[str, str]] | None = None,
) -> list[conversation.Content]:
    """Create a conversation with history (multiple turns)."""
    if turns is None:
        turns = [
            ("user", "What's the temperature in the bedroom?"),
            ("assistant", "The bedroom temperature is 72°F."),
            ("user", "Is that comfortable?"),
        ]

    content: list[conversation.Content] = []
    for role, message in turns:
        if role == "user":
            content.append(conversation.UserContent(content=message))
        elif role == "assistant":
            content.append(
                conversation.AssistantContent(agent_id="test", content=message)
            )
    return content


def create_message_with_tool_use() -> list[conversation.Content]:
    """Create messages that require tool use."""
    return [
        conversation.SystemContent(
            content="You are a helpful home automation assistant with access to smart home controls."
        ),
        conversation.UserContent(
            content="Turn on all the lights in the house",
        ),
    ]


def create_message_with_tool_results() -> list[conversation.Content]:
    """Create messages with tool use and results."""
    return [
        conversation.SystemContent(
            content="You are a helpful home automation assistant."
        ),
        conversation.UserContent(
            content="What lights are currently on?",
        ),
        conversation.AssistantContent(
            agent_id="conversation.mock_entity",
            content=None,
            tool_calls=[
                llm.ToolInput(
                    id="tool_use_123",
                    tool_name="get_lights_status",
                    tool_args={"area": "all"},
                )
            ],
        ),
        conversation.ToolResultContent(
            agent_id="conversation.mock_entity",
            tool_call_id="tool_use_123",
            tool_name="get_lights_status",
            tool_result={"lights": ["living_room", "kitchen"], "count": 2},
        ),
    ]


def create_message_with_multiple_tool_results() -> list[conversation.Content]:
    """Create messages with multiple tool calls and results."""
    return [
        conversation.SystemContent(
            content="You are a helpful home automation assistant."
        ),
        conversation.UserContent(
            content="Check the temperature in all rooms and turn on the AC if needed",
        ),
        conversation.AssistantContent(
            agent_id="conversation.mock_entity",
            content=None,
            tool_calls=[
                llm.ToolInput(
                    id="tool_use_1",
                    tool_name="get_temperature",
                    tool_args={"room": "bedroom"},
                ),
                llm.ToolInput(
                    id="tool_use_2",
                    tool_name="get_temperature",
                    tool_args={"room": "living_room"},
                ),
                llm.ToolInput(
                    id="tool_use_3",
                    tool_name="get_temperature",
                    tool_args={"room": "kitchen"},
                ),
            ],
        ),
        conversation.ToolResultContent(
            agent_id="conversation.mock_entity",
            tool_call_id="tool_use_1",
            tool_name="get_temperature",
            tool_result={"temperature": 78, "unit": "F"},
        ),
        conversation.ToolResultContent(
            agent_id="conversation.mock_entity",
            tool_call_id="tool_use_2",
            tool_name="get_temperature",
            tool_result={"temperature": 76, "unit": "F"},
        ),
        conversation.ToolResultContent(
            agent_id="conversation.mock_entity",
            tool_call_id="tool_use_3",
            tool_name="get_temperature",
            tool_result={"temperature": 75, "unit": "F"},
        ),
    ]


def create_message_with_failed_tool_result() -> list[conversation.Content]:
    """Create messages with a failed tool execution."""
    return [
        conversation.UserContent(
            content="Turn on the lights in the garage",
        ),
        conversation.AssistantContent(
            agent_id="conversation.mock_entity",
            content=None,
            tool_calls=[
                llm.ToolInput(
                    id="tool_use_456",
                    tool_name="turn_on_lights",
                    tool_args={"location": "garage"},
                )
            ],
        ),
        conversation.ToolResultContent(
            agent_id="conversation.mock_entity",
            tool_call_id="tool_use_456",
            tool_name="turn_on_lights",
            tool_result={"error": "Device not found: garage lights"},
        ),
    ]


def create_message_with_attachments(
    attachments: list[dict] | None = None,
) -> list[conversation.Content]:
    """Create a message with image attachments."""
    if attachments is None:
        attachments = [{"url": "/media/local/image.jpg", "mime_type": "image/jpeg"}]

    attachment_list = [
        conversation.Attachment(
            media_content_id=att.get("url", att.get("path", "")),
            path=Path(att.get("url", att.get("path", ""))),
            mime_type=att["mime_type"],
        )
        for att in attachments
    ]

    return [
        conversation.UserContent(
            content="What do you see in this image?",
            attachments=attachment_list,
        )
    ]


def create_message_with_multiple_attachments() -> list[conversation.Content]:
    """Create a message with multiple attachments."""
    return [
        conversation.SystemContent(
            content="You are a helpful assistant that can analyze images and documents."
        ),
        conversation.UserContent(
            content="Compare these two images and tell me what's different",
            attachments=[
                conversation.Attachment(
                    media_content_id="media-source://media_source/local/before.jpg",
                    path=Path("/media/local/before.jpg"),
                    mime_type="image/jpeg",
                ),
                conversation.Attachment(
                    media_content_id="media-source://media_source/local/after.jpg",
                    path=Path("/media/local/after.jpg"),
                    mime_type="image/jpeg",
                ),
            ],
        ),
    ]


def create_message_with_pdf_attachment() -> list[conversation.Content]:
    """Create a message with PDF attachment."""
    return [
        conversation.UserContent(
            content="Summarize this document",
            attachments=[
                conversation.Attachment(
                    media_content_id="media-source://media_source/local/manual.pdf",
                    path=Path("/media/local/manual.pdf"),
                    mime_type="application/pdf",
                )
            ],
        )
    ]


def create_complex_conversation_with_tools_and_attachments() -> list[
    conversation.Content
]:
    """Create a complex conversation with history, tools, and attachments."""
    return [
        conversation.SystemContent(
            content="You are a comprehensive home automation and analysis assistant."
        ),
        conversation.UserContent(
            content="What's the current state of my home?",
        ),
        conversation.AssistantContent(
            agent_id="conversation.mock_entity",
            content=None,
            tool_calls=[
                llm.ToolInput(
                    id="tool_use_state",
                    tool_name="get_home_state",
                    tool_args={},
                )
            ],
        ),
        conversation.ToolResultContent(
            agent_id="conversation.mock_entity",
            tool_call_id="tool_use_state",
            tool_name="get_home_state",
            tool_result={"lights_on": 3, "temperature": 72, "doors_locked": True},
        ),
        conversation.AssistantContent(
            agent_id="conversation.mock_entity",
            content="Your home currently has 3 lights on, the temperature is 72°F, and all doors are locked.",
        ),
        conversation.UserContent(
            content="Here's a photo from my security camera. Is everything okay?",
            attachments=[
                conversation.Attachment(
                    media_content_id="media-source://media_source/local/camera_snapshot.jpg",
                    path=Path("/media/local/camera_snapshot.jpg"),
                    mime_type="image/jpeg",
                )
            ],
        ),
    ]


def create_message_requiring_multiple_tool_iterations() -> list[conversation.Content]:
    """Create a message that would require multiple tool iterations to resolve."""
    return [
        conversation.SystemContent(
            content="You are a home automation assistant. Use available tools to accomplish user requests."
        ),
        conversation.UserContent(
            content="Find the brightest room and turn off the lights there",
        ),
    ]


def create_message_with_thinking_content() -> list[conversation.Content]:
    """Create a message that might produce thinking content (Claude models)."""
    return [
        conversation.SystemContent(
            content="You are a home automation assistant. Think through your reasoning before responding."
        ),
        conversation.UserContent(
            content="Should I turn on the AC or open the windows given that it's 75°F inside and 68°F outside with low humidity?",
        ),
    ]


def create_empty_message() -> list[conversation.Content]:
    """Create an edge case with minimal content."""
    return [
        conversation.UserContent(
            content="Hello",
        )
    ]


def create_message_with_special_characters() -> list[conversation.Content]:
    """Create a message with special characters and Unicode."""
    return [
        conversation.UserContent(
            content="Turn on the lights in the café ☕ and set temperature to 20°C 🌡️",
        )
    ]


def create_message_with_very_long_content() -> list[conversation.Content]:
    """Create a message with very long content to test token limits."""
    long_text = " ".join(
        [
            f"This is sentence number {i} in a very long user message."
            for i in range(100)
        ]
    )
    return [
        conversation.UserContent(
            content=long_text,
        )
    ]


def create_message_with_tool_name_mapping() -> list[conversation.Content]:
    """Create messages that test tool name sanitization and mapping."""
    return [
        conversation.UserContent(
            content="Execute the complex automation",
        ),
        conversation.AssistantContent(
            agent_id="conversation.mock_entity",
            content=None,
            tool_calls=[
                llm.ToolInput(
                    id="tool_use_complex",
                    tool_name="my.complex-tool_name!",  # Requires sanitization
                    tool_args={"action": "execute"},
                )
            ],
        ),
        conversation.ToolResultContent(
            agent_id="conversation.mock_entity",
            tool_call_id="tool_use_complex",
            tool_name="my.complex-tool_name!",
            tool_result={"status": "success"},
        ),
    ]


def create_message_with_structured_output_request() -> list[conversation.Content]:
    """Create a message that would benefit from structured output."""
    return [
        conversation.UserContent(
            content="List all devices in my home with their current status in a structured format",
        )
    ]


def create_conversation_with_mixed_assistant_content() -> list[conversation.Content]:
    """Create conversation with assistant messages both with and without tool calls."""
    return [
        conversation.UserContent(
            content="What's the weather and turn on the porch light",
        ),
        conversation.AssistantContent(
            agent_id="conversation.mock_entity",
            content="Let me check the weather and control the light for you.",
            tool_calls=[
                llm.ToolInput(
                    id="tool_use_weather",
                    tool_name="get_weather",
                    tool_args={},
                ),
                llm.ToolInput(
                    id="tool_use_light",
                    tool_name="turn_on_light",
                    tool_args={"light_id": "porch"},
                ),
            ],
        ),
        conversation.ToolResultContent(
            agent_id="conversation.mock_entity",
            tool_call_id="tool_use_weather",
            tool_name="get_weather",
            tool_result={"temperature": 72, "condition": "sunny"},
        ),
        conversation.ToolResultContent(
            agent_id="conversation.mock_entity",
            tool_call_id="tool_use_light",
            tool_name="turn_on_light",
            tool_result={"status": "on"},
        ),
    ]


def create_message_with_json_in_content() -> list[conversation.Content]:
    """Create a message with JSON content that needs proper escaping."""
    return [
        conversation.UserContent(
            content='Set the thermostat with config: {"mode": "cool", "temp": 72}',
        )
    ]


def create_message_with_code_blocks() -> list[conversation.Content]:
    """Create a message with code blocks."""
    return [
        conversation.UserContent(
            content="""Here's an automation I want to create:
```yaml
automation:
  - trigger:
      platform: time
      at: "07:00:00"
    action:
      - service: light.turn_on
        target:
          entity_id: light.bedroom
```
Can you help implement this?""",
        )
    ]


# Test scenario descriptions for documentation
CHAT_LOG_SCENARIOS = {
    "simple_message": {
        "description": "Basic user message without tools or attachments",
        "fixture": create_simple_user_message,
        "expected_iterations": 1,
        "tests": ["basic message processing", "text response generation"],
    },
    "system_prompt": {
        "description": "Message with system prompt",
        "fixture": create_message_with_system_prompt,
        "expected_iterations": 1,
        "tests": ["system content handling", "system message extraction"],
    },
    "conversation_history": {
        "description": "Multi-turn conversation with history",
        "fixture": create_conversation_history,
        "expected_iterations": 1,
        "tests": ["message history preservation", "context awareness"],
    },
    "tool_use": {
        "description": "Message requiring tool execution",
        "fixture": create_message_with_tool_use,
        "expected_iterations": 2,
        "tests": ["tool detection", "tool call generation", "tool name mapping"],
    },
    "tool_results": {
        "description": "Conversation with tool results",
        "fixture": create_message_with_tool_results,
        "expected_iterations": 1,
        "tests": ["tool result processing", "tool result to message conversion"],
    },
    "multiple_tools": {
        "description": "Multiple tool calls in one turn",
        "fixture": create_message_with_multiple_tool_results,
        "expected_iterations": 1,
        "tests": ["multiple tool handling", "tool result grouping"],
    },
    "failed_tool": {
        "description": "Tool execution failure",
        "fixture": create_message_with_failed_tool_result,
        "expected_iterations": 1,
        "tests": ["tool error handling", "error message processing"],
    },
    "image_attachment": {
        "description": "Message with image attachment",
        "fixture": create_message_with_attachments,
        "expected_iterations": 1,
        "tests": ["image attachment processing", "media source handling"],
    },
    "multiple_attachments": {
        "description": "Message with multiple attachments",
        "fixture": create_message_with_multiple_attachments,
        "expected_iterations": 1,
        "tests": ["multiple attachment handling", "attachment ordering"],
    },
    "pdf_attachment": {
        "description": "Message with PDF attachment",
        "fixture": create_message_with_pdf_attachment,
        "expected_iterations": 1,
        "tests": ["PDF processing", "document attachment handling"],
    },
    "complex_conversation": {
        "description": "Complex conversation with history, tools, and attachments",
        "fixture": create_complex_conversation_with_tools_and_attachments,
        "expected_iterations": 1,
        "tests": [
            "mixed content handling",
            "conversation flow",
            "context preservation",
        ],
    },
    "multiple_iterations": {
        "description": "Message requiring multiple tool iterations",
        "fixture": create_message_requiring_multiple_tool_iterations,
        "expected_iterations": 3,
        "tests": [
            "iteration loop",
            "sequential tool execution",
            "iteration limit enforcement",
        ],
    },
    "thinking_content": {
        "description": "Message producing thinking content (Claude models)",
        "fixture": create_message_with_thinking_content,
        "expected_iterations": 1,
        "tests": ["thinking tag removal", "DeepThink handling"],
    },
    "empty_message": {
        "description": "Minimal edge case message",
        "fixture": create_empty_message,
        "expected_iterations": 1,
        "tests": ["minimal input handling", "empty content edge cases"],
    },
    "special_characters": {
        "description": "Message with Unicode and special characters",
        "fixture": create_message_with_special_characters,
        "expected_iterations": 1,
        "tests": ["Unicode handling", "special character encoding"],
    },
    "long_content": {
        "description": "Very long message testing token limits",
        "fixture": create_message_with_very_long_content,
        "expected_iterations": 1,
        "tests": ["token limit handling", "truncation behavior"],
    },
    "tool_name_mapping": {
        "description": "Tool names requiring sanitization",
        "fixture": create_message_with_tool_name_mapping,
        "expected_iterations": 1,
        "tests": ["tool name sanitization", "bidirectional name mapping"],
    },
    "structured_output": {
        "description": "Request requiring structured output",
        "fixture": create_message_with_structured_output_request,
        "expected_iterations": 1,
        "tests": ["structured output generation", "schema enforcement"],
    },
    "mixed_assistant_content": {
        "description": "Assistant messages with mixed content types",
        "fixture": create_conversation_with_mixed_assistant_content,
        "expected_iterations": 1,
        "tests": ["mixed assistant content", "content + tool calls"],
    },
    "json_content": {
        "description": "Message containing JSON that needs escaping",
        "fixture": create_message_with_json_in_content,
        "expected_iterations": 1,
        "tests": ["JSON escaping", "special character handling"],
    },
    "code_blocks": {
        "description": "Message with code blocks",
        "fixture": create_message_with_code_blocks,
        "expected_iterations": 1,
        "tests": ["code block preservation", "multi-line content"],
    },
}
