"""Support for Wyoming intent recognition services."""

import logging
from typing import Any, Literal

from wyoming.asr import Transcript
from wyoming.client import AsyncTcpClient
from wyoming.handle import Handled, NotHandled
from wyoming.info import HandleProgram, IntentProgram
from wyoming.intent import Intent, NotRecognized

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
        while True:
            event = await client.read_event()
            if event is None:
                raise WyomingError("Connection lost")

            if Intent.is_type(event.type):
                # Success
                recognized_intent = Intent.from_event(event)
                _LOGGER.debug("Recognized intent: %s", recognized_intent)

                intent_type = recognized_intent.name
                intent_slots = {
                    e.name: {"value": e.value} for e in recognized_intent.entities
                }

                # Add to trace and chat log
                conversation.async_conversation_trace_append(
                    conversation.ConversationTraceEventType.TOOL_CALL,
                    {
                        "intent_name": intent_type,
                        "slots": intent_slots,
                    },
                )
                tool_input = llm.ToolInput(
                    tool_name=intent_type,
                    tool_args=intent_slots,
                    external=True,
                )
                chat_log.async_add_assistant_content_without_tools(
                    conversation.AssistantContent(
                        agent_id=user_input.agent_id,
                        content=None,
                        tool_calls=[tool_input],
                    )
                )
                intent_response = await intent.async_handle(
                    self.hass,
                    DOMAIN,
                    intent_type,
                    intent_slots,
                    text_input=user_input.text,
                    language=user_input.language,
                    satellite_id=user_input.satellite_id,
                    device_id=user_input.device_id,
                )

                if (not intent_response.speech) and recognized_intent.text:
                    response_text = recognized_intent.text
                    if template.is_template_string(response_text):
                        # Render text as a template
                        response_text = self._render_speech_template(
                            response_text, intent_response, intent_slots
                        )

                    intent_response.async_set_speech(response_text)

                break

            if NotRecognized.is_type(event.type):
                # Intent was not recognized
                not_recognized = NotRecognized.from_event(event)
                intent_response.async_set_error(
                    intent.IntentResponseErrorCode.NO_INTENT_MATCH,
                    not_recognized.text or "",
                )
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
