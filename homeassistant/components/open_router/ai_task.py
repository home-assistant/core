"""AI Task integration for OpenRouter."""

import base64
from json import JSONDecodeError
import logging
from typing import override

from python_open_router import Modality

from homeassistant.components import ai_task, conversation
from homeassistant.config_entries import ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.json import json_loads

from . import OpenRouterConfigEntry
from .const import CONF_OUTPUT_MODALITIES
from .entity import OpenRouterEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: OpenRouterConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up AI Task entities."""
    for subentry in config_entry.subentries.values():
        if subentry.subentry_type != "ai_task_data":
            continue

        async_add_entities(
            [OpenRouterAITaskEntity(config_entry, subentry)],
            config_subentry_id=subentry.subentry_id,
        )


class OpenRouterAITaskEntity(
    ai_task.AITaskEntity,
    OpenRouterEntity,
):
    """OpenRouter AI Task entity."""

    _attr_name = None

    def __init__(self, entry: OpenRouterConfigEntry, subentry: ConfigSubentry) -> None:
        """Initialize the entity."""
        super().__init__(entry, subentry)
        self._attr_supported_features = (
            ai_task.AITaskEntityFeature.GENERATE_DATA
            | ai_task.AITaskEntityFeature.SUPPORT_ATTACHMENTS
        )
        if Modality.IMAGE in subentry.data.get(CONF_OUTPUT_MODALITIES, []):
            self._attr_supported_features |= ai_task.AITaskEntityFeature.GENERATE_IMAGE

    @override
    async def _async_generate_data(
        self,
        task: ai_task.GenDataTask,
        chat_log: conversation.ChatLog,
    ) -> ai_task.GenDataTaskResult:
        """Handle a generate data task."""
        await self._async_handle_chat_log(chat_log, task.name, task.structure)

        if not isinstance(chat_log.content[-1], conversation.AssistantContent):
            raise HomeAssistantError(
                "Last content in chat log is not an AssistantContent"
            )

        text = chat_log.content[-1].content or ""

        if not task.structure:
            return ai_task.GenDataTaskResult(
                conversation_id=chat_log.conversation_id,
                data=text,
            )
        try:
            data = json_loads(text)
        except JSONDecodeError as err:
            raise HomeAssistantError(
                "Error with OpenRouter structured response"
            ) from err

        return ai_task.GenDataTaskResult(
            conversation_id=chat_log.conversation_id,
            data=data,
        )

    async def _async_generate_image(
        self,
        task: ai_task.GenImageTask,
        chat_log: conversation.ChatLog,
    ) -> ai_task.GenImageTaskResult:
        """Handle a generate image task."""
        await self._async_handle_chat_log(chat_log, force_image=True)

        content = chat_log.content[-1]
        if not isinstance(content, conversation.AssistantContent):
            raise HomeAssistantError(
                "Last content in chat log is not an AssistantContent"
            )

        if not content.native:
            raise HomeAssistantError("No image returned")

        # OpenRouter returns images as data URIs: `data:image/png;base64,<data>`
        try:
            image_url: str = content.native[0]["image_url"]["url"]
            metadata, _, encoded = image_url.partition(",")
            image_data = base64.b64decode(encoded, validate=True)
        except (LookupError, TypeError, ValueError) as err:
            raise HomeAssistantError("Invalid image returned") from err

        mime_type = metadata.removeprefix("data:").split(";")[0]
        if not metadata.startswith("data:") or not mime_type or not image_data:
            raise HomeAssistantError("Invalid image returned")

        return ai_task.GenImageTaskResult(
            image_data=image_data,
            conversation_id=chat_log.conversation_id,
            mime_type=mime_type,
            model=self.model,
        )
