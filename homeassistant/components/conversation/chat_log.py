"""Conversation chat log."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, AsyncIterable, Callable, Generator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import asdict, dataclass, field, replace
import logging
from typing import Any, Literal, TypedDict

import voluptuous as vol

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, TemplateError
from homeassistant.helpers import chat_session, intent, llm, template
from homeassistant.util.hass_dict import HassKey
from homeassistant.util.json import JsonObjectType

from . import trace
from .const import DOMAIN
from .models import ConversationInput, ConversationResult

DATA_CHAT_LOGS: HassKey[dict[str, ChatLog]] = HassKey("conversation_chat_logs")

LOGGER = logging.getLogger(__name__)

current_chat_log: ContextVar[ChatLog | None] = ContextVar(
    "current_chat_log", default=None
)


@contextmanager
def async_get_chat_log(
    hass: HomeAssistant,
    session: chat_session.ChatSession,
    user_input: ConversationInput | None = None,
    *,
    chat_log_delta_listener: Callable[[ChatLog, dict], None] | None = None,
) -> Generator[ChatLog]:
    """Return chat log for a specific chat session."""
    # If a chat log is already active and it's the requested conversation ID,
    # return that. We won't update the last updated time in this case.
    if (
        chat_log := current_chat_log.get()
    ) and chat_log.conversation_id == session.conversation_id:
        if chat_log_delta_listener is not None:
            raise RuntimeError(
                "Cannot attach chat log delta listener unless initial caller"
            )
        if user_input is not None and (
            (content := chat_log.content[-1]).role != "user"
            or content.content != user_input.text
        ):
            chat_log.async_add_user_content(UserContent(content=user_input.text))

        yield chat_log
        return

    all_chat_logs = hass.data.get(DATA_CHAT_LOGS)
    if all_chat_logs is None:
        all_chat_logs = {}
        hass.data[DATA_CHAT_LOGS] = all_chat_logs

    if chat_log := all_chat_logs.get(session.conversation_id):
        chat_log = replace(chat_log, content=chat_log.content.copy())
    else:
        chat_log = ChatLog(hass, session.conversation_id)

    if chat_log_delta_listener:
        chat_log.delta_listener = chat_log_delta_listener

    if user_input is not None:
        chat_log.async_add_user_content(UserContent(content=user_input.text))

    last_message = chat_log.content[-1]

    token = current_chat_log.set(chat_log)
    yield chat_log
    current_chat_log.reset(token)

    if chat_log.content[-1] is last_message:
        LOGGER.debug(
            "Chat Log opened but no assistant message was added, ignoring update"
        )
        return

    if session.conversation_id not in all_chat_logs:

        @callback
        def do_cleanup() -> None:
            """Handle cleanup."""
            all_chat_logs.pop(session.conversation_id)

        session.async_on_cleanup(do_cleanup)

    if chat_log_delta_listener:
        chat_log.delta_listener = None

    all_chat_logs[session.conversation_id] = chat_log


class ConverseError(HomeAssistantError):
    """Error during initialization of conversation.

    Will not be stored in the history.
    """

    def __init__(
        self, message: str, conversation_id: str, response: intent.IntentResponse
    ) -> None:
        """Initialize the error."""
        super().__init__(message)
        self.conversation_id = conversation_id
        self.response = response

    def as_conversation_result(self) -> ConversationResult:
        """Return the error as a conversation result."""
        return ConversationResult(
            response=self.response,
            conversation_id=self.conversation_id,
        )


@dataclass(frozen=True)
class SystemContent:
    """Base class for chat messages."""

    role: Literal["system"] = field(init=False, default="system")
    content: str


@dataclass(frozen=True)
class UserContent:
    """Assistant content."""

    role: Literal["user"] = field(init=False, default="user")
    content: str


@dataclass(frozen=True)
class AssistantContent:
    """Assistant content."""

    role: Literal["assistant"] = field(init=False, default="assistant")
    agent_id: str
    content: str | None = None
    tool_calls: list[llm.ToolInput] | None = None


@dataclass(frozen=True)
class ToolResultContent:
    """Tool result content."""

    role: Literal["tool_result"] = field(init=False, default="tool_result")
    agent_id: str
    tool_call_id: str
    tool_name: str
    tool_result: JsonObjectType


type Content = SystemContent | UserContent | AssistantContent | ToolResultContent


class AssistantContentDeltaDict(TypedDict, total=False):
    """Partial content to define an AssistantContent."""

    role: Literal["assistant"]
    content: str | None
    tool_calls: list[llm.ToolInput] | None


@dataclass
class ChatLog:
    """Class holding the chat history of a specific conversation."""

    hass: HomeAssistant
    conversation_id: str
    content: list[Content] = field(default_factory=lambda: [SystemContent(content="")])
    extra_system_prompt: str | None = None
    llm_api: llm.APIInstance | None = None
    delta_listener: Callable[[ChatLog, dict], None] | None = None

    @property
    def continue_conversation(self) -> bool:
        """Return whether the conversation should continue."""
        if not self.content:
            return False

        last_msg = self.content[-1]

        return (
            last_msg.role == "assistant"
            and last_msg.content is not None
            and last_msg.content.strip().endswith(
                (
                    "?",
                    ";",  # Greek question mark
                )
            )
        )

    @property
    def unresponded_tool_results(self) -> bool:
        """Return if there are unresponded tool results."""
        return self.content[-1].role == "tool_result"

    @callback
    def async_add_user_content(self, content: UserContent) -> None:
        """Add user content to the log."""
        LOGGER.debug("Adding user content: %s", content)
        self.content.append(content)

    @callback
    def async_add_assistant_content_without_tools(
        self, content: AssistantContent
    ) -> None:
        """Add assistant content to the log."""
        LOGGER.debug("Adding assistant content: %s", content)
        if content.tool_calls is not None:
            raise ValueError("Tool calls not allowed")
        self.content.append(content)

    async def async_add_assistant_content(
        self,
        content: AssistantContent,
        /,
        tool_call_tasks: dict[str, asyncio.Task] | None = None,
    ) -> AsyncGenerator[ToolResultContent]:
        """Add assistant content and execute tool calls.

        tool_call_tasks can contains tasks for tool calls that are already in progress.

        This method is an async generator and will yield the tool results as they come in.
        """
        LOGGER.debug("Adding assistant content: %s", content)
        self.content.append(content)

        if content.tool_calls is None:
            return

        if self.llm_api is None:
            raise ValueError("No LLM API configured")

        if tool_call_tasks is None:
            tool_call_tasks = {}
        for tool_input in content.tool_calls:
            if tool_input.id not in tool_call_tasks:
                tool_call_tasks[tool_input.id] = self.hass.async_create_task(
                    self.llm_api.async_call_tool(tool_input),
                    name=f"llm_tool_{tool_input.id}",
                )

        for tool_input in content.tool_calls:
            LOGGER.debug(
                "Tool call: %s(%s)", tool_input.tool_name, tool_input.tool_args
            )

            try:
                tool_result = await tool_call_tasks[tool_input.id]
            except (HomeAssistantError, vol.Invalid) as e:
                tool_result = {"error": type(e).__name__}
                if str(e):
                    tool_result["error_text"] = str(e)
            LOGGER.debug("Tool response: %s", tool_result)

            response_content = ToolResultContent(
                agent_id=content.agent_id,
                tool_call_id=tool_input.id,
                tool_name=tool_input.tool_name,
                tool_result=tool_result,
            )
            self.content.append(response_content)
            yield response_content

    async def async_add_delta_content_stream(
        self, agent_id: str, stream: AsyncIterable[AssistantContentDeltaDict]
    ) -> AsyncGenerator[AssistantContent | ToolResultContent]:
        """Stream content into the chat log.

        Returns a generator with all content that was added to the chat log.

        stream iterates over dictionaries with optional keys role, content and tool_calls.

        When a delta contains a role key, the current message is considered complete and
        a new message is started.

        The keys content and tool_calls will be concatenated if they appear multiple times.
        """
        current_content = ""
        current_tool_calls: list[llm.ToolInput] = []
        tool_call_tasks: dict[str, asyncio.Task] = {}

        async for delta in stream:
            LOGGER.debug("Received delta: %s", delta)

            # Indicates update to current message
            if "role" not in delta:
                if delta_content := delta.get("content"):
                    current_content += delta_content
                if delta_tool_calls := delta.get("tool_calls"):
                    if self.llm_api is None:
                        raise ValueError("No LLM API configured")
                    current_tool_calls += delta_tool_calls

                    # Start processing the tool calls as soon as we know about them
                    for tool_call in delta_tool_calls:
                        tool_call_tasks[tool_call.id] = self.hass.async_create_task(
                            self.llm_api.async_call_tool(tool_call),
                            name=f"llm_tool_{tool_call.id}",
                        )
                if self.delta_listener:
                    self.delta_listener(self, delta)  # type: ignore[arg-type]
                continue

            # Starting a new message

            if delta["role"] != "assistant":
                raise ValueError(f"Only assistant role expected. Got {delta['role']}")

            # Yield the previous message if it has content
            if current_content or current_tool_calls:
                content = AssistantContent(
                    agent_id=agent_id,
                    content=current_content or None,
                    tool_calls=current_tool_calls or None,
                )
                yield content
                async for tool_result in self.async_add_assistant_content(
                    content, tool_call_tasks=tool_call_tasks
                ):
                    yield tool_result
                    if self.delta_listener:
                        self.delta_listener(self, asdict(tool_result))

            current_content = delta.get("content") or ""
            current_tool_calls = delta.get("tool_calls") or []

            if self.delta_listener:
                self.delta_listener(self, delta)  # type: ignore[arg-type]

        if current_content or current_tool_calls:
            content = AssistantContent(
                agent_id=agent_id,
                content=current_content or None,
                tool_calls=current_tool_calls or None,
            )
            yield content
            async for tool_result in self.async_add_assistant_content(
                content, tool_call_tasks=tool_call_tasks
            ):
                yield tool_result
                if self.delta_listener:
                    self.delta_listener(self, asdict(tool_result))

    async def async_update_llm_data(
        self,
        conversing_domain: str,
        user_input: ConversationInput,
        user_llm_hass_api: str | None = None,
        user_llm_prompt: str | None = None,
    ) -> None:
        """Set the LLM system prompt."""
        llm_context = llm.LLMContext(
            platform=conversing_domain,
            context=user_input.context,
            user_prompt=user_input.text,
            language=user_input.language,
            assistant=DOMAIN,
            device_id=user_input.device_id,
        )

        llm_api: llm.APIInstance | None = None

        if user_llm_hass_api:
            try:
                llm_api = await llm.async_get_api(
                    self.hass,
                    user_llm_hass_api,
                    llm_context,
                )
            except HomeAssistantError as err:
                LOGGER.error(
                    "Error getting LLM API %s for %s: %s",
                    user_llm_hass_api,
                    conversing_domain,
                    err,
                )
                intent_response = intent.IntentResponse(language=user_input.language)
                intent_response.async_set_error(
                    intent.IntentResponseErrorCode.UNKNOWN,
                    "Error preparing LLM API",
                )
                raise ConverseError(
                    f"Error getting LLM API {user_llm_hass_api}",
                    conversation_id=self.conversation_id,
                    response=intent_response,
                ) from err

        user_name: str | None = None

        if (
            user_input.context
            and user_input.context.user_id
            and (
                user := await self.hass.auth.async_get_user(user_input.context.user_id)
            )
        ):
            user_name = user.name

        try:
            prompt_parts = [
                template.Template(
                    llm.BASE_PROMPT
                    + (user_llm_prompt or llm.DEFAULT_INSTRUCTIONS_PROMPT),
                    self.hass,
                ).async_render(
                    {
                        "ha_name": self.hass.config.location_name,
                        "user_name": user_name,
                        "llm_context": llm_context,
                    },
                    parse_result=False,
                )
            ]

        except TemplateError as err:
            LOGGER.error("Error rendering prompt: %s", err)
            intent_response = intent.IntentResponse(language=user_input.language)
            intent_response.async_set_error(
                intent.IntentResponseErrorCode.UNKNOWN,
                "Sorry, I had a problem with my template",
            )
            raise ConverseError(
                "Error rendering prompt",
                conversation_id=self.conversation_id,
                response=intent_response,
            ) from err

        if llm_api:
            prompt_parts.append(llm_api.api_prompt)

        if extra_system_prompt := (
            # Take new system prompt if one was given
            user_input.extra_system_prompt or self.extra_system_prompt
        ):
            prompt_parts.append(extra_system_prompt)

        prompt = "\n".join(prompt_parts)

        self.llm_api = llm_api
        self.extra_system_prompt = extra_system_prompt
        self.content[0] = SystemContent(content=prompt)

        LOGGER.debug("Prompt: %s", self.content)
        LOGGER.debug("Tools: %s", self.llm_api.tools if self.llm_api else None)

        self.async_trace(
            {
                "messages": self.content,
                "tools": self.llm_api.tools if self.llm_api else None,
            }
        )

    def async_trace(self, agent_details: dict[str, Any]) -> None:
        """Append agent specific details to the conversation trace."""
        trace.async_conversation_trace_append(
            trace.ConversationTraceEventType.AGENT_DETAIL,
            agent_details,
        )
