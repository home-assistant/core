"""Tests for the Interactions API helpers in Google Generative AI Conversation."""

from typing import override
from unittest.mock import AsyncMock, MagicMock

from google.genai import interactions
from google.genai.types import HarmCategory
import probatio
import pytest

from homeassistant.components import conversation
from homeassistant.components.google_generative_ai_conversation.const import (
    CONF_CHAT_MODEL,
    CONF_DANGEROUS_BLOCK_THRESHOLD,
    CONF_HARASSMENT_BLOCK_THRESHOLD,
    CONF_HATE_BLOCK_THRESHOLD,
    CONF_MAX_TOKENS,
    CONF_SEXUAL_BLOCK_THRESHOLD,
    CONF_TEMPERATURE,
    CONF_THINKING_LEVEL,
    CONF_TOP_K,
    CONF_TOP_P,
    RECOMMENDED_CHAT_MODEL,
)
from homeassistant.components.google_generative_ai_conversation.entity import (
    ContentDetails,
    PartDetails,
)
from homeassistant.components.google_generative_ai_conversation.interactions import (
    build_interaction_request,
    create_safety_settings,
    format_response_format,
    format_tools_for_interactions,
    transform_interactions_stream,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import llm


def test_format_tools_for_interactions() -> None:
    """Test formatting LLM tools for Interactions API."""

    class MockTool(llm.Tool):
        name = "test_tool"
        description = "A test tool"
        parameters = probatio.Schema(
            {
                probatio.Required("location"): str,
                probatio.Required("count"): int,
            }
        )

        @override
        async def async_call(
            self,
            hass: HomeAssistant,
            tool_input: llm.ToolInput,
            llm_context: llm.LLMContext,
        ) -> llm.ToolResult:
            return llm.ToolResult(data={})

    tool = MockTool()

    formatted = format_tools_for_interactions([tool])
    assert formatted == [
        interactions.Function(
            name="test_tool",
            description="A test tool",
            parameters={
                "type": "object",
                "properties": {
                    "location": {"type": "string"},
                    "count": {"type": "integer"},
                },
                "required": ["location", "count"],
                "additionalProperties": False,
            },
        )
    ]


def test_format_tools_google_search() -> None:
    """Test formatting Google Search tool for Interactions API."""
    formatted = format_tools_for_interactions([], enable_google_search=True)
    assert formatted == [interactions.GoogleSearch()]

    formatted_none = format_tools_for_interactions(None, enable_google_search=True)
    assert formatted_none == [interactions.GoogleSearch()]


def test_format_response_format() -> None:
    """Test formatting response_format for structured output."""
    assert format_response_format(None) is None

    schema = probatio.Schema({probatio.Required("status"): str})
    formatted = format_response_format(schema)
    assert formatted == interactions.TextResponseFormat(
        type="text",
        mime_type="application/json",
        schema_={
            "type": "object",
            "properties": {
                "status": {"type": "string"},
            },
            "required": ["status"],
            "additionalProperties": False,
        },
    )


def test_create_safety_settings() -> None:
    """Test creating safety settings from options."""
    options = {
        CONF_HATE_BLOCK_THRESHOLD: "BLOCK_LOW_AND_ABOVE",
        CONF_HARASSMENT_BLOCK_THRESHOLD: "BLOCK_MEDIUM_AND_ABOVE",
        CONF_DANGEROUS_BLOCK_THRESHOLD: "BLOCK_ONLY_HIGH",
        CONF_SEXUAL_BLOCK_THRESHOLD: "BLOCK_NONE",
    }
    settings = create_safety_settings(options)
    assert len(settings) == 4
    categories = {s.category: s.threshold for s in settings}
    assert categories[HarmCategory.HARM_CATEGORY_HATE_SPEECH] == "BLOCK_LOW_AND_ABOVE"
    assert categories[HarmCategory.HARM_CATEGORY_HARASSMENT] == "BLOCK_MEDIUM_AND_ABOVE"
    assert categories[HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT] == "BLOCK_ONLY_HIGH"
    assert categories[HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT] == "BLOCK_NONE"


def test_build_interaction_request_store_false_enforced() -> None:
    """Test build_interaction_request strictly enforces store=False."""
    request = build_interaction_request(
        model=RECOMMENDED_CHAT_MODEL,
        input_content="Hello world",
    )
    assert request["store"] is False
    assert request["stream"] is True

    with pytest.raises(
        ValueError,
        match="Home Assistant interactions must be stateless \\(store=False\\)",
    ):
        build_interaction_request(
            model=RECOMMENDED_CHAT_MODEL,
            input_content="Hello world",
            store=True,
        )


def test_build_interaction_request_full_parameters() -> None:
    """Test build_interaction_request with comprehensive parameters."""
    options = {
        CONF_CHAT_MODEL: "gemini-3.1-flash-lite",
        CONF_TEMPERATURE: 0.7,
        CONF_TOP_P: 0.9,
        CONF_TOP_K: 40,
        CONF_MAX_TOKENS: 1500,
        CONF_THINKING_LEVEL: "high",
    }
    safety_settings = create_safety_settings({})
    tools = [interactions.GoogleSearch()]
    response_format = interactions.TextResponseFormat(
        type="text", mime_type="application/json", schema_={}
    )

    request = build_interaction_request(
        model="gemini-3.1-flash-lite",
        input_content=[
            {"type": "user_input", "content": [{"type": "text", "text": "Hi"}]}
        ],
        options=options,
        system_instruction="You are a helpful assistant.",
        tools=tools,
        response_format=response_format,
        safety_settings=safety_settings,
        stream=True,
    )

    assert request["model"] == "gemini-3.1-flash-lite"
    assert request["store"] is False
    assert request["stream"] is True
    assert request["system_instruction"] == "You are a helpful assistant."
    assert request["tools"] == tools
    assert request["response_format"] == response_format
    assert request["safety_settings"] == safety_settings
    assert request["generation_config"] == {
        "temperature": 0.7,
        "top_p": 0.9,
        "top_k": 40,
        "max_output_tokens": 1500,
        "thinking_level": "high",
    }


async def test_transform_interactions_stream_text() -> None:
    """Test streaming text events from Interactions API."""
    chat_log = MagicMock()

    async def mock_events():
        yield interactions.StepStart(
            index=0,
            step=interactions.ModelOutputStep(),
        )
        yield interactions.StepDelta(
            index=0,
            delta=interactions.TextDelta(text="Hello, "),
        )
        yield interactions.StepDelta(
            index=0,
            delta=interactions.TextDelta(text="world!"),
            metadata=interactions.StepDeltaMetadata(
                total_usage=interactions.Usage(
                    total_input_tokens=10,
                    total_cached_tokens=0,
                    total_output_tokens=5,
                )
            ),
        )
        yield interactions.StepStop(index=0)
        yield interactions.InteractionCompletedEvent(
            interaction=interactions.InteractionSseEventInteraction(
                id="int_1",
                status="completed",
                created="",
                model="gemini-2.5-flash",
                object="interaction",
                updated="",
            ),
        )

    deltas = [
        delta async for delta in transform_interactions_stream(chat_log, mock_events())
    ]

    assert deltas == [
        {"role": "assistant"},
        {"content": "Hello, "},
        {"content": "world!"},
    ]

    chat_log.async_trace.assert_called_with(
        {
            "stats": {
                "input_tokens": 10,
                "cached_input_tokens": 0,
                "output_tokens": 5,
            }
        }
    )


async def test_transform_interactions_stream_thinking_and_signature() -> None:
    """Test streaming thinking content and signatures from Interactions API."""
    chat_log = MagicMock()

    async def mock_events():
        yield interactions.StepStart(
            index=0,
            step=interactions.ThoughtStep(),
        )
        yield interactions.StepDelta(
            index=0,
            delta=interactions.ThoughtSummaryDelta(
                content=interactions.TextContent(text="Thinking deeply..."),
            ),
        )
        yield interactions.StepDelta(
            index=0,
            delta=interactions.ThoughtSignatureDelta(
                signature="dGVzdF9zaWdfMTIz",
            ),
        )
        yield interactions.StepStop(index=0)
        yield interactions.StepStart(
            index=1,
            step=interactions.ModelOutputStep(),
        )
        yield interactions.StepDelta(
            index=1,
            delta=interactions.TextDelta(text="Result."),
        )
        yield interactions.StepStop(index=1)

    deltas = [
        delta async for delta in transform_interactions_stream(chat_log, mock_events())
    ]

    assert deltas[0] == {"role": "assistant"}
    assert deltas[1] == {"thinking_content": "Thinking deeply..."}
    assert deltas[2] == {"content": "Result."}
    assert deltas[3] == {
        "native": ContentDetails(
            part_details=[
                PartDetails(
                    part_type="thought",
                    index=18,
                    length=0,
                    thought_signature="dGVzdF9zaWdfMTIz",
                )
            ]
        )
    }


async def test_transform_interactions_stream_thought_summary_nested_content() -> None:
    """Test streaming thought summary with nested content text."""
    chat_log = MagicMock()

    async def mock_events():
        yield interactions.StepStart(
            index=0,
            step=interactions.ThoughtStep(),
        )
        yield interactions.StepDelta(
            index=0,
            delta=interactions.ThoughtSummaryDelta(
                content=interactions.TextContent(text="Summarized reasoning"),
            ),
        )
        yield interactions.StepStop(index=0)

    deltas = [
        delta async for delta in transform_interactions_stream(chat_log, mock_events())
    ]

    assert deltas == [
        {"role": "assistant"},
        {"thinking_content": "Summarized reasoning"},
    ]


async def test_transform_interactions_stream_tool_calls_streamed() -> None:
    """Test streaming tool calls with argument deltas from Interactions API."""
    chat_log = MagicMock()

    async def mock_events():
        yield interactions.StepStart(
            index=0,
            step=interactions.FunctionCallStep(
                id="call_123",
                name="turn_on",
                arguments={},
            ),
        )
        yield interactions.StepDelta(
            index=0,
            delta=interactions.ArgumentsDelta(
                arguments='{"entity_id": ',
            ),
        )
        yield interactions.StepDelta(
            index=0,
            delta=interactions.ArgumentsDelta(
                arguments='"light.living_room"}',
            ),
        )
        yield interactions.StepStop(index=0)

    deltas = [
        delta async for delta in transform_interactions_stream(chat_log, mock_events())
    ]

    assert deltas[0] == {"role": "assistant"}
    assert deltas[1] == {
        "tool_calls": [
            llm.ToolInput(
                tool_name="turn_on",
                tool_args={"entity_id": "light.living_room"},
                id="call_123",
            )
        ]
    }


async def test_transform_interactions_stream_prepopulated_tool_calls() -> None:
    """Test tool calls with pre-populated arguments from Interactions API."""
    chat_log = MagicMock()

    async def mock_events():
        yield interactions.StepStart(
            index=0,
            step=interactions.FunctionCallStep(
                id="call_456",
                name="turn_off",
                arguments={"entity_id": "switch.ac"},
            ),
        )
        yield interactions.StepStop(index=0)

    deltas = [
        delta async for delta in transform_interactions_stream(chat_log, mock_events())
    ]

    assert deltas[0] == {"role": "assistant"}
    assert deltas[1] == {
        "tool_calls": [
            llm.ToolInput(
                tool_name="turn_off",
                tool_args={"entity_id": "switch.ac"},
                id="call_456",
            )
        ]
    }


async def test_transform_interactions_stream_error_event() -> None:
    """Test handling error event in stream."""
    chat_log = MagicMock()

    async def mock_events():
        yield interactions.ErrorEvent(
            error=interactions.Error(message="Resource exhausted"),
        )

    with pytest.raises(HomeAssistantError, match="Resource exhausted"):
        async for _ in transform_interactions_stream(chat_log, mock_events()):
            pass


async def test_transform_interactions_stream_status_update_failed() -> None:
    """Test handling failed interaction.status_update event."""
    chat_log = MagicMock()

    async def mock_events():
        yield interactions.InteractionStatusUpdate(
            interaction_id="int_123",
            status="failed",
        )

    with pytest.raises(HomeAssistantError, match="Status: failed"):
        async for _ in transform_interactions_stream(chat_log, mock_events()):
            pass


async def test_transform_interactions_stream_failed_interaction() -> None:
    """Test handling failed status in stream."""
    chat_log = MagicMock()

    async def mock_events():
        yield interactions.InteractionCompletedEvent(
            interaction=interactions.InteractionSseEventInteraction(
                id="int_123",
                status="failed",
                created="",
                model="gemini-2.5-flash",
                object="interaction",
                updated="",
            ),
        )

    with pytest.raises(HomeAssistantError, match="Status: failed"):
        async for _ in transform_interactions_stream(chat_log, mock_events()):
            pass


async def test_transform_interactions_stream_gemini_3_flash_userland_tool(
    hass: HomeAssistant,
) -> None:
    """Test replaying recorded gemini-3.8-flash userland tool stream."""
    chat_log = conversation.ChatLog(hass, "test_conversation")
    chat_log.async_add_user_content(
        conversation.UserContent(content="What is the weather in Paris?")
    )

    thought_sig = (
        "EqoCCqcCAWkUfRONClarNa03RQrCGMaxi0NTu82KpbT8/abhCrrvMnl6S/6xaxVtzhGlRl4D5aw"
        "lHf8QTp7nV/ScNr2Zfzgwv7LRxZTiGiD4hnWZFepxHB79iPbs+SRi0RdkgEjN3gB3xsPIwQb1TX"
        "ilkcRXD7F/iebZF68uokCv0/asYbuUgvFyb567dBbi5qVuKDeMyFOVyqAOCSl5Tj4lQyy+8+Im8"
        "KGi+modccOZ1TdeHQnd3lAk6qCok6nOA8oiT2tg2Ck44KmsBCEJSYBqYr7XOhheKK8y/A8lqs0D"
        "LdLQzfxdoVQyvv1dYfeQaiBc2j5E0K2K3gJoWo0UTjG/C1EtYLek6ttpcM1hfnuS8SvJKx3OLi+"
        "CDEil7uZOmA1a5AfpTOSf8Kqzug=="
    )

    async def mock_events():
        yield interactions.InteractionCreatedEvent(
            interaction=interactions.InteractionSseEventInteraction(
                id="",
                status="in_progress",
                model="gemini-3.8-flash",
                object="interaction",
            )
        )
        yield interactions.InteractionStatusUpdate(
            interaction_id="",
            status="in_progress",
        )
        yield interactions.StepStart(
            index=0,
            step=interactions.ThoughtStep(),
        )
        yield interactions.StepDelta(
            index=0,
            delta=interactions.ThoughtSignatureDelta(signature=thought_sig),
        )
        yield interactions.StepStop(index=0)
        yield interactions.StepStart(
            index=1,
            step=interactions.FunctionCallStep(
                arguments={},
                id="call_647382",
                name="get_weather",
            ),
        )
        yield interactions.StepDelta(
            index=1,
            delta=interactions.ArgumentsDelta(arguments='{"location":"Paris"}'),
        )
        yield interactions.StepStop(index=1)
        yield interactions.InteractionCompletedEvent(
            interaction=interactions.InteractionSseEventInteraction(
                id="",
                status="requires_action",
                model="gemini-3.8-flash",
                object="interaction",
            )
        )

    chat_log.llm_api = MagicMock()
    chat_log.llm_api.async_call_tool = AsyncMock(
        return_value=llm.ToolResult(data={"temperature": "18°C"})
    )

    contents = [
        c
        async for c in chat_log.async_add_delta_content_stream(
            "test_agent", transform_interactions_stream(chat_log, mock_events())
        )
    ]

    assistant_content = next(
        c for c in contents if isinstance(c, conversation.AssistantContent)
    )
    assert assistant_content.tool_calls == [
        llm.ToolInput(
            tool_name="get_weather",
            tool_args={"location": "Paris"},
            id="call_647382",
        )
    ]
    assert assistant_content.native == ContentDetails(
        part_details=[
            PartDetails(
                part_type="thought",
                index=0,
                length=0,
                thought_signature=thought_sig,
            )
        ]
    )
    assert assistant_content.native.part_details[0].thought_signature == thought_sig


async def test_transform_interactions_stream_gemini_3_flash_google_search(
    hass: HomeAssistant,
) -> None:
    """Test replaying recorded gemini-3.8-flash Google Search stream."""
    chat_log = conversation.ChatLog(hass, "test_conversation")
    chat_log.async_add_user_content(
        conversation.UserContent(content="who won Super Bowl LX 2026?")
    )

    search_sig = (
        "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"
        "PTm/JT4O49I/+iQ=="
    )

    thought_sig = (
        "EuUSCuISAWkUfROUQtSdFAxbHyCEz9ttYVg3MCN1Opxxge6vZnWcDUyakfBipBz5fzX0Lg3e67t"
        "dJp+asAxC2BuqWMtDTckCjWT+QJYLYhJHXsOvgdSj/lIK8BRiJWJ8BhV95l5vv6kV4KvQotEUk/"
        "mKtZ0HqsWZYcGUueCIuuYckhauH4Sy8EKL+58MnTDuZUlmsVvAhh0c5qFsHr6RSyHIsQBY70tgt"
        "13vtOMajtqiLpFoLJnBy3siv4OGmCohFav+PJvOrUBBgGkBEJ7IRpx6gIw0c3ST2ntS9ZscJFQK"
        "sfVzin6lw6qYVJgzr1hdn/+CY/aoGyzvKBYf1cPsymtnwjAEYCoerAZHqYBR89yl/BydjGz4hIl"
        "uvQyIOteUrH59IadyhCnKMOxxIqXND2qEmN8r/o32vR+VtKe4J88FQfMpnd/ki+0ZltZOducyF9"
        "rs2GIYcDhDkDiXL4yFlPedbQ8ssT0UgEn4CtlSVkgHxWOPRpCy/0sdAnDWktBNu7bJsbTnXgMPh"
        "c+40zBs4ppwNCGm95XPhUIsGHzENO+ZA//0MN5dCye6pCrQzKwDbS95skJiXfZwCdsnOdL2a9f4"
        "Qa0zo1Lkm7hvCCyJEPdOnPc4D3N7Aah6wD/uDofsbH9G/BBCM/AByt1o86WdMuQM9/LFI/YpWo0"
        "O0vsGHsV2qhEksaZt25GtP4gakPEHttH6FzE45r5uwAdtW00GQBmgnMDS5c7bTX0gZaIyY5R7xW"
        "+tESPouWL7tt8/k+Ix1SwpKc01rjMb6y8zjb+tpMN6O3WNN8wb6jZkmUMkXB2QDgdBej+6iA+kG"
        "nZMlBVHLqaIfyimh4yqRJCwbLtn2NiVMtH4+uHCUlWYNsJe27B37o5X7Y05EO7I0ItUe8i3TTba"
        "lhy17ohfH3tHximYOSwa3jJfT/OrRRkdw5c+YLf15urCJMLs66oM7e2sklhb0tAkXSFbkBbout8"
        "zpCH/7luDGOsz/GPmXilr7ABwysN9LzfHjwXICHBRdLyxSCLmBVwXlOZ0yo9afova6xaHRSkirt"
        "cwLPl/JZEHZJjvm9eyIWjNqSGuUuSmUUimgne/Gu13IqDqYODqcKOvMmO3doLB85ScfUrFcSCwB"
        "cA55pCzB94eJSWqJqVx7bnAxPBTmyck/758kBX8nMAfdmba3EGccGrrsaT+Ydyo03lutTb55VMA"
        "oLnUuEUWwIWGmqT7S8Sjg5p9+2TCU0CUQ8mCI2vBrvu/FOSrR8nBpzhDhaYdJWJm9hh8USed7ES"
        "JqrfZvF8kEx91ptn5l4Oq0arqNMwaIusuLNptn7ubttmAws2rHudyiYHzfyiy8iPrC8gUJ/ht8e"
        "h6aLcMT83LJi6r7zAkE0uiVIYEBTXbHy1L4CZokRg4fPyQ2B1Tkzyu22yOYthewnvLZk1aXz3Ri"
        "lsPDlD3AhRN4rl7VJJ8tZO9A7UWs4x8NE+MNPq6L5sV3cMb7Sozc8VatoPOyPc287MLnoFTH6wr"
        "//XC2lsnYC+eOxbXb9p3/hrciLytScEbyyNQ7ie9Qag/jnC4oiWyKRe/zFnIuORtolvredEA+HJ"
        "kLUuLZxQq6u4Ohm9GC3drr2/Y0h9sc3+KYni5YluVzn8MtH5G5X2eRKlE+dgJ5GI9AZ/JZ813l5"
        "vH/6IRhyqIMneqz07hwwBrauyQuSbdRkLPRYlX2tiBNXPociPC3yD/zh5fMDNNKEVOzBV9szEHm"
        "4tel6ID/6E4ChnVtOwvHzyZ8HhkTOQ7DosqbmZzagipi1P73ZHEotM1JKN2AObT4dI6orGBHqZn"
        "yqgFwjo/0CJTUK2/mc3SF0I23Ghr+Pm71xB9dMX2CSe/2TL0Dyvq4TiTEBBq4aPfmpzbSbVDY1s"
        "EARaa/OqPekHAVR/ItNzpeTTqbMKy9keZer3Xla/u41DrbtKBRhkHHMMsumLTjukrsIOat1ImUM"
        "f8TWZOICVa2QWZ11QuhRmSl7VsEyrvlDrdEBWAB9ETT/t91ZFoxDj+4MnAORWeGkUhXlOsDJ4bC"
        "a0r6hVW+tMWpJAAeq3jQ/IOu0tueW1DBbIpMF7JgvX0kKrCKDW+ZVz/YDJVFjo4Mw64V4UfHd15"
        "6P/M6OgBSF081P2W2a0mlwOYCyR0LPzGbug7JChx3TrjPDuk3mFuPXKH6Wo2GtSxDk9l1eQkRIo"
        "gM7k5bd4ScDld/dn0R1PP0zGc7+owdpKTNFMaff3jupuw7SInIl1IGn0bdgU8l70AdKojcYgCYm"
        "6KV1I+38hHYfNNQMKIErZDk8C7H6tJndFZvwWOGTP40uEU2q3307T6PSMXqHDFWBLjNmNLl/CQ"
        "WbZkQVQbjkaXAjsQI3NUaTUmBH/isXa9ieLgmS1KUf2ppHvZUqlaquWykhTgQCzofBldXIyWxTN"
        "x8ZiU3C3OWrFRQ5txIaECeh1aoVp3m0aqMdzzYE8ZRitjaUs+kyDMD1TwlU7C3YMn4BzDefU0oY"
        "EKt1cd+kCS1/3gRT+WRIjToSlQ/y/Svi+mlc6JEEhd10SPQtIS9RMb+xLBKr8Ik6HnDjAEqot6D"
        "z8aVdifokGmYbESAMm3UzGITS3adS3TeVOR5TIcRt974Y0ipMGQ0dRy8EclDdVvDuOBmJeKg7nr"
        "QlyC/Vnwo2Dxr3KicfarfHwYwyjvfh5vYoskjOLdyvpqbr7AqrubdzXDeCUugTuoRlEAKTM2qYL"
        "DpBH2sgUdF6s751HVeANwK2a574aPpMahnSYvK0R/G8DACHMFF5WsUzQAMYxQa8UpR87DcNaG2W"
        "9D2J3EyyKN5h3B7C2V7bLb7b2z7f//kFI2pknXdQ8pmi8xVzE810pIVII2U5Nje7nFm8naYEGR"
        "X6UvCcKs+BEZtg/G9tYGk5ZjGwsZI7qH9366kWmzalxZvcy6sTpdbj9WbHPl8gxyUrF9tfCzNu3"
        "EGa+6F7S9RbO+8PH/d7+dx4Sa56Go/ymbuEKZiEyYDzGI5YkOgnvOSOWt/xJbesIVxsIPRS3Hf+"
        "rsfGmyxEv39FJtaez8/gZsg9LLP+Pj8LRNSZKwIp3mav+tTsiGZv/44EYPtXFB3EJZwpowNfQKU"
        "P5l3dYiLZqaOKAYNnKi6nn0j6GQhq4kKEcQ7Y1zxkGraCjFLaEv9LRjt48MenAU2w6T+nTVfvrU"
        "14YkBdWPmYtIvUH5ju92fvN229UdOkcPNuEJFd/INaQuS4J2tvTAo2fvYfe/A7w="
    )

    async def mock_events():
        yield interactions.InteractionCreatedEvent(
            interaction=interactions.InteractionSseEventInteraction(
                id="",
                status="in_progress",
                model="gemini-3.8-flash",
                object="interaction",
            )
        )
        yield interactions.InteractionStatusUpdate(
            interaction_id="",
            status="in_progress",
        )
        yield interactions.StepStart(
            index=0,
            step=interactions.GoogleSearchCallStep(
                arguments=interactions.GoogleSearchCallArguments(queries=None),
                id="call_491782",
                signature="",
            ),
        )
        yield interactions.StepDelta(
            index=0,
            delta=interactions.GoogleSearchCallDelta(
                arguments=interactions.GoogleSearchCallArguments(
                    queries=[
                        "Super Bowl LX 2026 winner",
                        "Super Bowl LX date location",
                    ]
                ),
                signature=search_sig,
            ),
        )
        yield interactions.StepStop(index=0)
        yield interactions.StepStart(
            index=1,
            step=interactions.GoogleSearchResultStep(
                call_id="call_491782",
                result=[],
                signature="",
            ),
        )
        yield interactions.StepDelta(
            index=1,
            delta=interactions.GoogleSearchResultDelta(
                result=[interactions.GoogleSearchResult(search_suggestions="...")],
                signature="res_sig_abc",
            ),
        )
        yield interactions.StepStop(index=1)
        yield interactions.StepStart(
            index=2,
            step=interactions.ThoughtStep(),
        )
        yield interactions.StepDelta(
            index=2,
            delta=interactions.ThoughtSignatureDelta(signature=thought_sig),
        )
        yield interactions.StepStop(index=2)
        yield interactions.StepStart(
            index=3,
            step=interactions.ModelOutputStep(),
        )
        yield interactions.StepDelta(
            index=3,
            delta=interactions.TextDelta(
                text="The **Seattle Seahawks** won Super Bowl LX on February 8, 2026."
            ),
        )
        yield interactions.StepStop(index=3)
        yield interactions.InteractionCompletedEvent(
            interaction=interactions.InteractionSseEventInteraction(
                id="",
                status="completed",
                model="gemini-3.8-flash",
                object="interaction",
            )
        )

    contents = [
        c
        async for c in chat_log.async_add_delta_content_stream(
            "test_agent", transform_interactions_stream(chat_log, mock_events())
        )
    ]

    assistant_content = next(
        c for c in contents if isinstance(c, conversation.AssistantContent)
    )
    assert (
        assistant_content.content
        == "The **Seattle Seahawks** won Super Bowl LX on February 8, 2026."
    )
    assert assistant_content.tool_calls == [
        llm.ToolInput(
            tool_name="google_search",
            tool_args={
                "queries": [
                    "Super Bowl LX 2026 winner",
                    "Super Bowl LX date location",
                ]
            },
            id="call_491782",
            external=True,
        )
    ]
    assert assistant_content.native == ContentDetails(
        part_details=[
            PartDetails(
                part_type="google_search_call",
                index=0,
                length=0,
                thought_signature=search_sig,
            ),
            PartDetails(
                part_type="thought",
                index=0,
                length=0,
                thought_signature=thought_sig,
            ),
        ]
    )
    assert assistant_content.native.part_details[0].thought_signature == search_sig
    assert assistant_content.native.part_details[1].thought_signature == thought_sig
