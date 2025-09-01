"""Entity for the AI Task integration."""

from collections.abc import AsyncGenerator
import contextlib
from typing import final

from propcache.api import cached_property

from homeassistant.components.conversation import (
    ChatLog,
    UserContent,
    async_get_chat_log,
)
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.helpers import llm
from homeassistant.helpers.chat_session import ChatSession
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import dt as dt_util

from .const import DEFAULT_SYSTEM_PROMPT, DOMAIN, AITaskEntityFeature
from .task import GenDataTask, GenDataTaskResult, GenImageTask, GenImageTaskResult


class AITaskEntity(RestoreEntity):
    """Entity that supports conversations."""

    _attr_should_poll = False
    _attr_supported_features = AITaskEntityFeature(0)
    __last_activity: str | None = None

    @property
    @final
    def state(self) -> str | None:
        """Return the state of the entity."""
        if self.__last_activity is None:
            return None
        return self.__last_activity

    @cached_property
    def supported_features(self) -> AITaskEntityFeature:
        """Flag supported features."""
        return self._attr_supported_features

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
    @contextlib.asynccontextmanager
    async def _async_get_ai_task_chat_log(
        self,
        session: ChatSession,
        task: GenDataTask | GenImageTask,
    ) -> AsyncGenerator[ChatLog]:
        """Context manager used to manage the ChatLog used during an AI Task."""
        # pylint: disable-next=contextmanager-generator-missing-cleanup
        with (
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

            chat_log.async_add_user_content(
                UserContent(task.instructions, attachments=task.attachments)
            )

            yield chat_log

    @final
    async def internal_async_generate_data(
        self,
        session: ChatSession,
        task: GenDataTask,
    ) -> GenDataTaskResult:
        """Run a gen data task."""
        self.__last_activity = dt_util.utcnow().isoformat()
        self.async_write_ha_state()
        async with self._async_get_ai_task_chat_log(session, task) as chat_log:
            return await self._async_generate_data(task, chat_log)

    async def _async_generate_data(
        self,
        task: GenDataTask,
        chat_log: ChatLog,
    ) -> GenDataTaskResult:
        """Handle a gen data task."""
        raise NotImplementedError

    @final
    async def internal_async_generate_image(
        self,
        session: ChatSession,
        task: GenImageTask,
    ) -> GenImageTaskResult:
        """Run a gen image task."""
        self.__last_activity = dt_util.utcnow().isoformat()
        self.async_write_ha_state()
        async with self._async_get_ai_task_chat_log(session, task) as chat_log:
            return await self._async_generate_image(task, chat_log)

    async def _async_generate_image(
        self,
        task: GenImageTask,
        chat_log: ChatLog,
    ) -> GenImageTaskResult:
        """Handle a gen image task."""
        raise NotImplementedError
