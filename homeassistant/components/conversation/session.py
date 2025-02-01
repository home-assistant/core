"""Conversation history."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
import logging
from typing import Literal

import voluptuous as vol

from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    HassJob,
    HassJobType,
    HomeAssistant,
    callback,
)
from homeassistant.exceptions import HomeAssistantError, TemplateError
from homeassistant.helpers import intent, llm, template
from homeassistant.helpers.event import async_call_later
from homeassistant.util import dt as dt_util, ulid as ulid_util
from homeassistant.util.hass_dict import HassKey
from homeassistant.util.json import JsonObjectType

from . import trace
from .const import DOMAIN
from .models import ConversationInput, ConversationResult

DATA_CHAT_HISTORY: HassKey[dict[str, ChatSession]] = HassKey(
    "conversation_chat_session"
)
DATA_CHAT_HISTORY_CLEANUP: HassKey[SessionCleanup] = HassKey(
    "conversation_chat_session_cleanup"
)

LOGGER = logging.getLogger(__name__)
CONVERSATION_TIMEOUT = timedelta(minutes=5)


class SessionCleanup:
    """Helper to clean up the history."""

    unsub: CALLBACK_TYPE | None = None

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the history cleanup."""
        self.hass = hass
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, self._on_hass_stop)
        self.cleanup_job = HassJob(
            self._cleanup, "conversation_history_cleanup", job_type=HassJobType.Callback
        )

    @callback
    def schedule(self) -> None:
        """Schedule the cleanup."""
        if self.unsub:
            return
        self.unsub = async_call_later(
            self.hass,
            CONVERSATION_TIMEOUT.total_seconds() + 1,
            self.cleanup_job,
        )

    @callback
    def _on_hass_stop(self, event: Event) -> None:
        """Cancel the cleanup on shutdown."""
        if self.unsub:
            self.unsub()
        self.unsub = None

    @callback
    def _cleanup(self, now: datetime) -> None:
        """Clean up the history and schedule follow-up if necessary."""
        self.unsub = None
        all_history = self.hass.data[DATA_CHAT_HISTORY]

        # We mutate original object because current commands could be
        # yielding history based on it.
        for conversation_id, history in list(all_history.items()):
            if history.last_updated + CONVERSATION_TIMEOUT < now:
                del all_history[conversation_id]

        # Still conversations left, check again in timeout time.
        if all_history:
            self.schedule()


@asynccontextmanager
async def async_get_chat_session(
    hass: HomeAssistant,
    user_input: ConversationInput,
) -> AsyncGenerator[ChatSession]:
    """Return chat session."""
    all_history = hass.data.get(DATA_CHAT_HISTORY)
    if all_history is None:
        all_history = {}
        hass.data[DATA_CHAT_HISTORY] = all_history
        hass.data[DATA_CHAT_HISTORY_CLEANUP] = SessionCleanup(hass)

    history: ChatSession | None = None

    if user_input.conversation_id is None:
        conversation_id = ulid_util.ulid_now()

    elif history := all_history.get(user_input.conversation_id):
        conversation_id = user_input.conversation_id

    else:
        # Conversation IDs are ULIDs. We generate a new one if not provided.
        # If an old OLID is passed in, we will generate a new one to indicate
        # a new conversation was started. If the user picks their own, they
        # want to track a conversation and we respect it.
        try:
            ulid_util.ulid_to_bytes(user_input.conversation_id)
            conversation_id = ulid_util.ulid_now()
        except ValueError:
            conversation_id = user_input.conversation_id

    if history:
        history = replace(history, messages=history.messages.copy())
    else:
        history = ChatSession(hass, conversation_id, user_input.agent_id)

    message: Content = Content(
        role="user",
        agent_id=user_input.agent_id,
        content=user_input.text,
    )
    history.async_add_message(message)

    yield history

    if history.messages[-1] is message:
        LOGGER.debug(
            "History opened but no assistant message was added, ignoring update"
        )
        return

    history.last_updated = dt_util.utcnow()
    all_history[conversation_id] = history
    hass.data[DATA_CHAT_HISTORY_CLEANUP].schedule()


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


@dataclass
class Content:
    """Base class for chat messages."""

    role: Literal["system", "assistant", "user"]
    agent_id: str | None
    content: str


@dataclass(frozen=True)
class NativeContent[_NativeT]:
    """Native content."""

    role: str = field(init=False, default="native")
    agent_id: str
    content: _NativeT


@dataclass
class ChatSession[_NativeT]:
    """Class holding all information for a specific conversation."""

    hass: HomeAssistant
    conversation_id: str
    agent_id: str | None
    user_name: str | None = None
    messages: list[Content | NativeContent[_NativeT]] = field(
        default_factory=lambda: [Content(role="system", agent_id=None, content="")]
    )
    extra_system_prompt: str | None = None
    llm_api: llm.APIInstance | None = None
    last_updated: datetime = field(default_factory=dt_util.utcnow)

    @callback
    def async_add_message(self, message: Content | NativeContent[_NativeT]) -> None:
        """Process intent."""
        if message.role == "system":
            raise ValueError("Cannot add system messages to history")
        if message.role != "native" and self.messages[-1].role == message.role:
            raise ValueError("Cannot add two assistant or user messages in a row")

        self.messages.append(message)

    @callback
    def async_get_messages(
        self, agent_id: str | None = None
    ) -> list[Content | NativeContent[_NativeT]]:
        """Get messages for a specific agent ID.

        This will filter out any native message tied to other agent IDs.
        It can still include assistant/user messages generated by other agents.
        """
        return [
            message
            for message in self.messages
            if message.role != "native" or message.agent_id == agent_id
        ]

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

        extra_system_prompt = (
            # Take new system prompt if one was given
            user_input.extra_system_prompt or self.extra_system_prompt
        )

        if extra_system_prompt:
            prompt_parts.append(extra_system_prompt)

        prompt = "\n".join(prompt_parts)

        self.llm_api = llm_api
        self.user_name = user_name
        self.extra_system_prompt = extra_system_prompt
        self.messages[0] = Content(
            role="system",
            agent_id=user_input.agent_id,
            content=prompt,
        )

        LOGGER.debug("Prompt: %s", self.messages)
        LOGGER.debug("Tools: %s", self.llm_api.tools if self.llm_api else None)

        trace.async_conversation_trace_append(
            trace.ConversationTraceEventType.AGENT_DETAIL,
            {
                "messages": self.messages,
                "tools": self.llm_api.tools if self.llm_api else None,
            },
        )

    async def async_call_tool(self, tool_input: llm.ToolInput) -> JsonObjectType:
        """Invoke LLM tool for the configured LLM API."""
        if not self.llm_api:
            raise ValueError("No LLM API configured")
        LOGGER.debug("Tool call: %s(%s)", tool_input.tool_name, tool_input.tool_args)

        try:
            tool_response = await self.llm_api.async_call_tool(tool_input)
        except (HomeAssistantError, vol.Invalid) as e:
            tool_response = {"error": type(e).__name__}
            if str(e):
                tool_response["error_text"] = str(e)
        LOGGER.debug("Tool response: %s", tool_response)
        return tool_response
