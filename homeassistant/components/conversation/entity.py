"""Entity for conversation integration."""

from abc import abstractmethod
from typing import Literal, final

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.helpers.chat_session import async_get_chat_session
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import dt as dt_util

from .chat_log import ChatLog, async_get_chat_log
from .const import ConversationEntityFeature
from .models import ConversationInput, ConversationResult


class ConversationEntity(RestoreEntity):
    """Entity that supports conversations."""

    _attr_should_poll = False
    _attr_supported_features = ConversationEntityFeature(0)
    __last_activity: str | None = None

    @property
    @final
    def state(self) -> str | None:
        """Return the state of the entity."""
        if self.__last_activity is None:
            return None
        return self.__last_activity

    async def async_internal_added_to_hass(self) -> None:
        """Call when the entity is added to hass."""
        await super().async_internal_added_to_hass()
        state = await self.async_get_last_state()
        if (
            state is not None
            and state.state is not None
            and state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN)
        ):
            self.__last_activity = state.state

    @final
    async def internal_async_process(
        self, user_input: ConversationInput
    ) -> ConversationResult:
        """Process a sentence."""
        self.__last_activity = dt_util.utcnow().isoformat()
        self.async_write_ha_state()
        return await self.async_process(user_input)

    @property
    @abstractmethod
    def supported_languages(self) -> list[str] | Literal["*"]:
        """Return a list of supported languages."""

    async def async_process(self, user_input: ConversationInput) -> ConversationResult:
        """Process a sentence."""
        with (
            async_get_chat_session(self.hass, user_input.conversation_id) as session,
            async_get_chat_log(self.hass, session, user_input) as chat_log,
        ):
            return await self._async_handle_message(user_input, chat_log)

    async def _async_handle_message(
        self,
        user_input: ConversationInput,
        chat_log: ChatLog,
    ) -> ConversationResult:
        """Call the API."""
        raise NotImplementedError

    async def async_prepare(self, language: str | None = None) -> None:
        """Load intents for a language."""
