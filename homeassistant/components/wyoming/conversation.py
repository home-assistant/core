"""Support for Wyoming intent recognition services."""

import asyncio
import logging
from typing import Any, Literal

from wyoming.asr import Transcript
from wyoming.client import AsyncTcpClient
from wyoming.handle import Handled, NotHandled
from wyoming.info import HandleProgram, IntentProgram
from wyoming.intent import Intent, IntentsStart, IntentsStop, NotRecognized

from homeassistant.components import conversation
from homeassistant.const import MATCH_ALL
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import TemplateError
from homeassistant.helpers import chat_session, intent, llm, template
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import ulid as ulid_util

from .const import DOMAIN
from .data import WyomingService
from .error import WyomingError
from .models import WyomingConfigEntry

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: WyomingConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Wyoming conversation."""
    item = config_entry.runtime_data
    async_add_entities(
        [
            WyomingConversationEntity(config_entry, item.service),
        ]
    )


class WyomingConversationEntity(
    conversation.ConversationEntity, conversation.AbstractConversationAgent
):
    """Wyoming conversation agent."""

    _attr_has_entity_name = True

    def __init__(
        self,
        config_entry: WyomingConfigEntry,
        service: WyomingService,
    ) -> None:
        """Set up provider."""
        super().__init__()

        self.service = service

        self._intent_service: IntentProgram | None = None
        self._handle_service: HandleProgram | None = None

        for maybe_intent in self.service.info.intent:
            if maybe_intent.installed:
                self._intent_service = maybe_intent
                break

        for maybe_handle in self.service.info.handle:
            if maybe_handle.installed:
                self._handle_service = maybe_handle
                break

        model_languages: set[str] = set()

        if self._intent_service is not None:
            for intent_model in self._intent_service.models:
                if intent_model.installed:
                    model_languages.update(intent_model.languages)

            self._attr_name = self._intent_service.name
            self._attr_supported_features = (
                conversation.ConversationEntityFeature.CONTROL
            )
        elif self._handle_service is not None:
            for handle_model in self._handle_service.models:
                if handle_model.installed:
                    model_languages.update(handle_model.languages)

            self._attr_name = self._handle_service.name
            if self._handle_service.supports_home_control:
                self._attr_supported_features = (
                    conversation.ConversationEntityFeature.CONTROL
                )

        self._supported_languages = list(model_languages)
        self._attr_unique_id = f"{config_entry.entry_id}-conversation"

    @property
    def supported_languages(self) -> list[str] | Literal["*"]:
        """Return a list of supported languages."""
        if not self._supported_languages:
            return MATCH_ALL

        return self._supported_languages

    async def async_process(
        self, user_input: conversation.ConversationInput
    ) -> conversation.ConversationResult:
        """Process a sentence."""
        conversation_id = user_input.conversation_id or ulid_util.ulid_now()
        intent_response = intent.IntentResponse(language=user_input.language)

        context = {"conversation_id": conversation_id}
        if user_input.device_id:
            context["device_id"] = user_input.device_id
        if user_input.satellite_id:
            context["satellite_id"] = user_input.satellite_id

        try:
            async with AsyncTcpClient(self.service.host, self.service.port) as client:
                await client.write_event(
                    Transcript(
                        user_input.text,
                        context=context,
                        language=user_input.language,
                    ).event()
                )
                with (
                    chat_session.async_get_chat_session(
                        self.hass, user_input.conversation_id
                    ) as session,
                    conversation.async_get_chat_log(
                        self.hass, session, user_input
                    ) as chat_log,
                ):
                    intent_response = await self._async_process(
                        user_input, client, chat_log, intent_response
                    )
        except (OSError, WyomingError) as err:
            _LOGGER.exception("Unexpected error while communicating with service")
            intent_response.async_set_error(
                intent.IntentResponseErrorCode.UNKNOWN,
                f"Error communicating with service: {err}",
            )
            return conversation.ConversationResult(
                response=intent_response,
                conversation_id=user_input.conversation_id,
            )
        except intent.IntentError as err:
            _LOGGER.exception("Unexpected error while handling intent")
            intent_response.async_set_error(
                intent.IntentResponseErrorCode.FAILED_TO_HANDLE,
                f"Error handling intent: {err}",
            )
            return conversation.ConversationResult(
                response=intent_response,
                conversation_id=user_input.conversation_id,
            )

        # Success
        return conversation.ConversationResult(
            response=intent_response, conversation_id=conversation_id
        )

    async def _async_process(
        self,
        user_input: conversation.ConversationInput,
        client: AsyncTcpClient,
        chat_log: conversation.ChatLog,
        intent_response: intent.IntentResponse,
    ) -> intent.IntentResponse:
        """Process a sentence into an intent response."""
        has_intents_list = False
        intents: list[Intent] = []

        while True:
            event = await client.read_event()
            if event is None:
                raise WyomingError("Connection lost")

            if IntentsStart.is_type(event.type):
                # Multiple intents may be present
                has_intents_list = True
                continue

            if Intent.is_type(event.type):
                intents.append(Intent.from_event(event))
                if not has_intents_list:
                    # Only one intent, no need to wait
                    break

            if IntentsStop.is_type(event.type):
                # End of intents list
                break

            if NotRecognized.is_type(event.type):
                # Intent was not recognized
                not_recognized = NotRecognized.from_event(event)
                intent_response.async_set_error(
                    intent.IntentResponseErrorCode.NO_INTENT_MATCH,
                    not_recognized.text or "",
                )

                # Don't process any intents if one was not recognized
                intents.clear()
                break

            if Handled.is_type(event.type):
                # Success
                handled = Handled.from_event(event)
                intent_response.async_set_speech(handled.text or "")
                break

            if NotHandled.is_type(event.type):
                # Command was not handled
                not_handled = NotHandled.from_event(event)
                intent_response.async_set_error(
                    intent.IntentResponseErrorCode.FAILED_TO_HANDLE,
                    not_handled.text or "",
                )
                break

        if not intents:
            return intent_response

        # Process recognized intents with a task group.
        # If any intent fails to be handled, the rest are cancelled.
        intent_responses: list[intent.IntentResponse] = []
        try:
            async with asyncio.TaskGroup() as task_group:
                intent_tasks: list[tuple[str, dict, str | None, asyncio.Task]] = []
                for recognized_intent in intents:
                    _LOGGER.debug("Handling intent: %s", recognized_intent)

                    intent_type = recognized_intent.name
                    intent_slots = {
                        e.name: {"value": e.value} for e in recognized_intent.entities
                    }

                    # Add to trace
                    conversation.async_conversation_trace_append(
                        conversation.ConversationTraceEventType.TOOL_CALL,
                        {
                            "intent_name": intent_type,
                            "slots": intent_slots,
                        },
                    )
                    intent_tasks.append(
                        (
                            intent_type,
                            intent_slots,
                            recognized_intent.text,
                            task_group.create_task(
                                intent.async_handle(
                                    self.hass,
                                    DOMAIN,
                                    intent_type,
                                    intent_slots,
                                    text_input=user_input.text,
                                    language=user_input.language,
                                    satellite_id=user_input.satellite_id,
                                    device_id=user_input.device_id,
                                )
                            ),
                        )
                    )

        except* intent.IntentError as err_group:
            # Bubble up first exception only.
            # There's nothing the caller can do with multiple intent errors.
            raise err_group.exceptions[0] from err_group

        # Gather intent handling results
        tool_calls: list[llm.ToolInput] = []
        for intent_type, intent_slots, intent_text, intent_task in intent_tasks:
            intent_task_response = await intent_task
            intent_responses.append(intent_task_response)

            # For the chat log
            tool_calls.append(
                llm.ToolInput(
                    tool_name=intent_type,
                    tool_args=intent_slots,
                    external=True,
                )
            )

            # Process speech
            if (not intent_task_response.speech) and intent_text:
                if template.is_template_string(intent_text):
                    # Render text as a template
                    intent_text = self._render_speech_template(
                        intent_text, intent_task_response, intent_slots
                    )

                intent_task_response.async_set_speech(intent_text)

        # Add all tool calls to the chat log
        chat_log.async_add_assistant_content_without_tools(
            conversation.AssistantContent(
                agent_id=user_input.agent_id,
                content=None,
                tool_calls=tool_calls,
            )
        )

        # Must be the case because an exception would have been thrown otherwise
        assert intent_responses

        # Use the properties of the first intent (response_type, etc.) and
        # combine the speech results.
        intent_response = intent_responses[0]
        speech_texts: list[str] = [
            speech
            for current_response in intent_responses
            if (speech := current_response.speech.get("plain", {}).get("speech"))
        ]

        if speech_texts:
            # Combine response with newlines because punctuation would be
            # language-dependent.
            intent_response.async_set_speech("\n".join(speech_texts))

        return intent_response

    def _render_speech_template(
        self,
        response_text: str,
        intent_response: intent.IntentResponse,
        intent_slots: dict[str, Any],
    ) -> str:
        """Render speech template with similar behavior to the default agent."""
        state1: State | None = None
        if intent_response.matched_states:
            state1 = intent_response.matched_states[0]
        elif intent_response.unmatched_states:
            state1 = intent_response.unmatched_states[0]

        # Render response template
        speech_slots = {name: value["value"] for name, value in intent_slots.items()}
        speech_slots.update(intent_response.speech_slots)

        response_template = template.Template(response_text, self.hass)
        try:
            speech = response_template.async_render(
                {
                    # Slots from intent recognizer and response
                    "slots": speech_slots,
                    # First matched or unmatched state
                    "state": (
                        template.TemplateState(self.hass, state1)
                        if state1 is not None
                        else None
                    ),
                    "query": {
                        # Entity states that matched the query (e.g, "on")
                        "matched": [
                            template.TemplateState(self.hass, state)
                            for state in intent_response.matched_states
                        ],
                        # Entity states that did not match the query
                        "unmatched": [
                            template.TemplateState(self.hass, state)
                            for state in intent_response.unmatched_states
                        ],
                    },
                }
            )
        except TemplateError:
            _LOGGER.exception("Unexpected error while rendering response")
            raise

        # Normalize whitespace
        if speech is not None:
            speech = str(speech)
            speech = " ".join(speech.strip().split())

        return speech
