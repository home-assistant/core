"""Support for Wyoming intent services."""
import logging
from typing import Literal

from wyoming.asr import Transcript
from wyoming.client import AsyncTcpClient
from wyoming.handle import Handled, NotHandled
from wyoming.info import HandleProgram, IntentProgram
from wyoming.intent import Intent, NotRecognized, Recognize

from homeassistant.components.conversation import agent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent

from .const import DOMAIN
from .data import WyomingService
from .error import WyomingError

_LOGGER = logging.getLogger(__name__)


class WyomingConversationError(WyomingError):
    """Base class for Wyoming conversation errors."""


class WyomingConversationAgent(agent.AbstractConversationAgent):
    """Wyoming conversation agent."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        service: WyomingService,
    ) -> None:
        """Set up provider."""
        self.hass = hass
        self.service = service
        self._intent_service: IntentProgram | None = None
        self._handle_service: HandleProgram | None = None

        for intent_program in service.info.intent:
            if intent_program.installed:
                self._intent_service = intent_program
                break

        for handle_program in service.info.handle:
            if handle_program.installed:
                self._handle_service = handle_program
                break

        self._supported_languages: list[str] = []
        if self._intent_service is not None:
            for intent_model in self._intent_service.models:
                self._supported_languages.extend(intent_model.languages)

            self._attr_name = self._intent_service.name
        elif self._handle_service is not None:
            for handle_model in self._handle_service.models:
                self._supported_languages.extend(handle_model.languages)

            self._attr_name = self._handle_service.name
        else:
            raise WyomingConversationError("No intent or handle services")

        self._attr_unique_id = f"{config_entry.entry_id}-conversation"

    @property
    def supported_languages(self) -> list[str] | Literal["*"]:
        """Return a list of supported languages."""
        return self._supported_languages

    async def async_process(
        self, user_input: agent.ConversationInput
    ) -> agent.ConversationResult:
        """Process a sentence."""
        if self._intent_service is not None:
            return await self._async_process_intent(user_input)

        if self._handle_service is not None:
            return await self._async_process_handle(user_input)

        raise WyomingConversationError("No intent or handle service")

    async def _async_process_intent(
        self, user_input: agent.ConversationInput
    ) -> agent.ConversationResult:
        try:
            async with AsyncTcpClient(self.service.host, self.service.port) as client:
                # Recognize -> Intent | NotRecognized
                await client.write_event(Recognize(user_input.text).event())
                result_event = await client.read_event()

                if result_event is not None:
                    if Intent.is_type(result_event.type):
                        result_intent = Intent.from_event(result_event)
                        _LOGGER.debug("Recognized intent: %s", result_intent)
                        intent_slots = {
                            e.name: {"value": e.value} for e in result_intent.entities
                        }
                        intent_response = await intent.async_handle(
                            self.hass,
                            DOMAIN,
                            intent_type=result_intent.name,
                            slots=intent_slots,
                            text_input=user_input.text,
                            context=user_input.context,
                            language=user_input.language,
                        )

                        return agent.ConversationResult(
                            response=intent_response,
                            conversation_id=user_input.conversation_id,
                        )

                    if NotRecognized.is_type(result_event.type):
                        _LOGGER.warning("No intent was recognized")

        except (OSError, WyomingError):
            _LOGGER.exception("Unexpected error during intent recognition")

        return _empty_result(user_input.language)

    async def _async_process_handle(
        self, user_input: agent.ConversationInput
    ) -> agent.ConversationResult:
        try:
            async with AsyncTcpClient(self.service.host, self.service.port) as client:
                # Transcript -> Handled | NotHandled
                await client.write_event(Transcript(user_input.text).event())
                result_event = await client.read_event()

                if Handled.is_type(result_event.type):
                    # Handled contains response text only
                    result_handled = Handled.from_event(result_event)
                    _LOGGER.debug("User input was handled: %s", result_handled)
                    response = intent.IntentResponse(user_input.language)
                    response.async_set_speech(result_handled.text)
                    return agent.ConversationResult(
                        response=response,
                        conversation_id=user_input.conversation_id,
                    )

                if NotHandled.is_type(result_event.type):
                    _LOGGER.warning("User input was not handled")

        except (OSError, WyomingError):
            _LOGGER.exception("Unexpected error during user input handling")

        return _empty_result(user_input.language)


def _empty_result(language: str) -> agent.ConversationResult:
    """Return an empty conversation result."""
    return agent.ConversationResult(response=intent.IntentResponse(language))
