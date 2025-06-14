"""Entity for the LLM Task integration."""

from abc import abstractmethod
from typing import final

from homeassistant.components.conversation import (
    ChatLog,
    UserContent,
    async_get_chat_log,
)
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.helpers import llm
from homeassistant.helpers.chat_session import async_get_chat_session
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import dt as dt_util

from .const import DEFAULT_SYSTEM_PROMPT, DOMAIN
from .task import LLMTask, LLMTaskResult


class LLMTaskEntity(RestoreEntity):
    """Entity that supports conversations."""

    _attr_should_poll = False
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
    async def internal_async_handle_llm_task(
        self,
        task: LLMTask,
    ) -> LLMTaskResult:
        """Run an LLM task."""
        self.__last_activity = dt_util.utcnow().isoformat()
        self.async_write_ha_state()
        with (
            async_get_chat_session(self.hass) as session,
            async_get_chat_log(
                self.hass,
                session,
                None,
            ) as chat_log,
        ):
            await chat_log.async_provide_llm_data(
                llm.LLMContext(
                    platform=self.platform.domain,
                    context=None,
                    language=None,
                    assistant=DOMAIN,
                    device_id=None,
                ),
                user_llm_prompt=DEFAULT_SYSTEM_PROMPT,
            )

            chat_log.async_add_user_content(UserContent(task.prompt))

            return await self._async_handle_llm_task(task, chat_log)

    @abstractmethod
    async def _async_handle_llm_task(
        self,
        task: LLMTask,
        chat_log: ChatLog,
    ) -> LLMTaskResult:
        """Handle an LLM task."""
        raise NotImplementedError
