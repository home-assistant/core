"""Support for Wyoming intent recognition services."""

import logging

from wyoming.asr import Transcript
from wyoming.client import AsyncTcpClient
from wyoming.handle import Handled, NotHandled
from wyoming.info import HandleProgram, IntentProgram
from wyoming.intent import Intent, NotRecognized

from homeassistant.components import conversation
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import ulid

from .const import DOMAIN
from .data import WyomingService
from .error import WyomingError
from .models import DomainDataItem

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Wyoming conversation."""
    item: DomainDataItem = hass.data[DOMAIN][config_entry.entry_id]
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
        config_entry: ConfigEntry,
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
    def supported_languages(self) -> list[str]:
        """Return a list of supported languages."""
        return self._supported_languages

    async def async_process(
        self, user_input: conversation.ConversationInput
    ) -> conversation.ConversationResult:
        """Process a sentence."""
        conversation_id = user_input.conversation_id or ulid.ulid_now()
        intent_response = intent.IntentResponse(language=user_input.language)

        try:
            async with AsyncTcpClient(self.service.host, self.service.port) as client:
                await client.write_event(
                    Transcript(
                        user_input.text, context={"conversation_id": conversation_id}
                    ).event()
                )

                while True:
                    event = await client.read_event()
                    if event is None:
                        _LOGGER.debug("Connection lost")
                        intent_response.async_set_error(
                            intent.IntentResponseErrorCode.UNKNOWN,
                            "Connection to service was lost",
                        )
                        return conversation.ConversationResult(
                            response=intent_response,
                            conversation_id=user_input.conversation_id,
                        )

                    if Intent.is_type(event.type):
                        # Success
                        recognized_intent = Intent.from_event(event)
                        _LOGGER.debug("Recognized intent: %s", recognized_intent)

                        intent_type = recognized_intent.name
                        intent_slots = {
                            e.name: {"value": e.value}
                            for e in recognized_intent.entities
                        }
                        intent_response = await intent.async_handle(
                            self.hass,
                            DOMAIN,
                            intent_type,
                            intent_slots,
                            text_input=user_input.text,
                            language=user_input.language,
                        )

                        if (not intent_response.speech) and recognized_intent.text:
                            intent_response.async_set_speech(recognized_intent.text)

                        break

                    if NotRecognized.is_type(event.type):
                        not_recognized = NotRecognized.from_event(event)
                        intent_response.async_set_error(
                            intent.IntentResponseErrorCode.NO_INTENT_MATCH,
                            not_recognized.text,
                        )
                        break

                    if Handled.is_type(event.type):
                        # Success
                        handled = Handled.from_event(event)
                        intent_response.async_set_speech(handled.text)
                        break

                    if NotHandled.is_type(event.type):
                        not_handled = NotHandled.from_event(event)
                        intent_response.async_set_error(
                            intent.IntentResponseErrorCode.FAILED_TO_HANDLE,
                            not_handled.text,
                        )
                        break

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
