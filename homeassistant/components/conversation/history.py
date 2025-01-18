"""Conversation history."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
import logging
from typing import Literal

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, TemplateError
from homeassistant.helpers import intent, llm, template
from homeassistant.util import dt as dt_util, ulid
from homeassistant.util.hass_dict import HassKey

from .const import DOMAIN
from .models import ConversationInput, ConversationResult

DATA_CHAT_HISTORY: HassKey["dict[str, ChatHistory]"] = HassKey(
    "conversation_chat_history"
)

LOGGER = logging.getLogger(__name__)
CONVERSATION_TIMEOUT = timedelta(minutes=5)


@asynccontextmanager
async def async_get_chat_history(
    hass: HomeAssistant,
    user_input: ConversationInput,
) -> AsyncGenerator["ChatHistory"]:
    """Return chat history."""
    all_history = hass.data.get(DATA_CHAT_HISTORY)
    if all_history is None:
        all_history = {}
        hass.data[DATA_CHAT_HISTORY] = all_history

    history: ChatHistory | None = None

    if user_input.conversation_id is None:
        conversation_id = ulid.ulid_now()

    elif history := all_history.get(user_input.conversation_id):
        # Expire if it's an old conversation
        if history.last_updated + CONVERSATION_TIMEOUT < dt_util.utcnow():
            del all_history[user_input.conversation_id]
            history = None
        else:
            conversation_id = user_input.conversation_id

    else:
        # Conversation IDs are ULIDs. We generate a new one if not provided.
        # If an old OLID is passed in, we will generate a new one to indicate
        # a new conversation was started. If the user picks their own, they
        # want to track a conversation and we respect it.
        try:
            ulid.ulid_to_bytes(user_input.conversation_id)
            conversation_id = ulid.ulid_now()
        except ValueError:
            conversation_id = user_input.conversation_id

    if history:
        history = replace(history, messages=history.messages.copy())
    else:
        history = ChatHistory(hass, conversation_id)

    yield history

    history.last_updated = dt_util.utcnow()
    all_history[conversation_id] = history


class ConverseError(HomeAssistantError):
    """Error during conversation."""

    def __init__(
        self, message: str, conversation_id: str, response: intent.IntentResponse
    ) -> None:
        """Initialize the error."""
        super().__init__(message)
        self.conversation_id = conversation_id
        self.response = response

    def as_converstation_result(self) -> ConversationResult:
        """Return the error as a conversation result."""
        return ConversationResult(
            response=self.response,
            conversation_id=self.conversation_id,
        )


@dataclass
class ChatMessage:
    """Base class for chat messages."""

    role: Literal["system", "user"]
    agent_id: str | None
    content: str


@dataclass
class ChatHistory:
    """Class holding all conversation info."""

    hass: HomeAssistant
    conversation_id: str
    user_name: str | None = None
    messages: list = field(
        default_factory=lambda: [ChatMessage(role="system", agent_id=None, content="")]
    )
    extra_system_prompt: str | None = None
    llm_api: llm.APIInstance | None = None
    last_updated: datetime = field(default_factory=dt_util.utcnow)

    @callback
    def async_add_message(self, message: ChatMessage) -> None:
        """Process intent."""
        if self.messages and self.messages[-1].role == message.role:
            raise ValueError("Cannot add two messages of the same role in a row")

        self.messages.append(message)

    @callback
    def async_process_intent_message(self, user_input: ConversationInput) -> None:
        """Process intent."""
        self.messages.append(
            ChatMessage(
                role="user",
                agent_id=user_input.agent_id,
                content=user_input.text,
            ),
        )

    async def async_process_llm_message(
        self,
        conversing_domain: str,
        user_input: ConversationInput,
        user_llm_hass_api: str | None = None,
        user_llm_prompt: str | None = None,
    ) -> None:
        """Process a new message."""
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
        self.messages[0] = ChatMessage(
            role="system",
            agent_id=user_input.agent_id,
            content=prompt,
        )
        self.messages.append(
            ChatMessage(
                role="user",
                agent_id=user_input.agent_id,
                content=user_input.text,
            )
        )
