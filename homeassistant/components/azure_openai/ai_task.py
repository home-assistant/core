"""AI Task integration for OpenAI."""

import base64
from json import JSONDecodeError
import logging
from typing import TYPE_CHECKING, override

from openai.types.responses.response_output_item import ImageGenerationCall

from homeassistant.components import ai_task, conversation
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.json import json_loads

from .capabilities import RECOMMENDED_IMAGE_MODEL, get_capabilities
from .const import CONF_IMAGE_DEPLOYMENT, CONF_IMAGE_MODEL, CONF_MODEL_FAMILY, DOMAIN
from .entity import OpenAIBaseLLMEntity

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigSubentry

    from . import OpenAIConfigEntry

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: OpenAIConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up AI Task entities."""
    for subentry in config_entry.subentries.values():
        if subentry.subentry_type != "ai_task_data":
            continue

        async_add_entities(
            [OpenAITaskEntity(config_entry, subentry)],
            config_subentry_id=subentry.subentry_id,
        )


class OpenAITaskEntity(
    ai_task.AITaskEntity,
    OpenAIBaseLLMEntity,
):
    """Azure OpenAI AI Task entity."""

    def __init__(self, entry: OpenAIConfigEntry, subentry: ConfigSubentry) -> None:
        """Initialize the entity."""
        super().__init__(entry, subentry)
        self._attr_supported_features = (
            ai_task.AITaskEntityFeature.GENERATE_DATA
            | ai_task.AITaskEntityFeature.SUPPORT_ATTACHMENTS
        )
        capabilities = get_capabilities(self.subentry.data.get(CONF_MODEL_FAMILY, ""))
        if "image" in capabilities.features and self.subentry.data.get(
            CONF_IMAGE_DEPLOYMENT
        ):
            self._attr_supported_features |= ai_task.AITaskEntityFeature.GENERATE_IMAGE

    @override
    async def _async_generate_data(
        self,
        task: ai_task.GenDataTask,
        chat_log: conversation.ChatLog,
    ) -> ai_task.GenDataTaskResult:
        """Handle a generate data task."""
        await self._async_handle_chat_log(
            chat_log, task.name, task.structure, max_iterations=1000
        )

        if not isinstance(chat_log.content[-1], conversation.AssistantContent):
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="unexpected_chat_log_content",
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
            _LOGGER.error("Failed to parse JSON response: %s", err)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="invalid_structured_response",
            ) from err

        return ai_task.GenDataTaskResult(
            conversation_id=chat_log.conversation_id,
            data=data,
        )

    @override
    async def _async_generate_image(
        self,
        task: ai_task.GenImageTask,
        chat_log: conversation.ChatLog,
    ) -> ai_task.GenImageTaskResult:
        """Handle a generate image task."""
        await self._async_handle_chat_log(chat_log, task.name, force_image=True)

        if not isinstance(chat_log.content[-1], conversation.AssistantContent):
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="unexpected_chat_log_content",
            )

        image_call: ImageGenerationCall | None = None
        for content in reversed(chat_log.content):
            if not isinstance(content, conversation.AssistantContent):
                break
            if isinstance(content.native, ImageGenerationCall):
                if image_call is None or image_call.result is None:
                    image_call = content.native
                else:  # Remove image data from chat log to save memory
                    content.native.result = None

        if image_call is None or image_call.result is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="no_image_returned",
            )

        image_data = base64.b64decode(image_call.result)
        image_call.result = None

        if hasattr(image_call, "output_format") and (
            output_format := image_call.output_format
        ):
            mime_type = f"image/{output_format}"
        else:
            mime_type = "image/png"

        if size := image_call.size:
            width, height = tuple(size.split("x"))
        else:
            width, height = None, None

        return ai_task.GenImageTaskResult(
            image_data=image_data,
            conversation_id=chat_log.conversation_id,
            mime_type=mime_type,
            width=int(width) if width else None,
            height=int(height) if height else None,
            model=self.subentry.data.get(CONF_IMAGE_MODEL, RECOMMENDED_IMAGE_MODEL),
            revised_prompt=image_call.revised_prompt
            if hasattr(image_call, "revised_prompt")
            else None,
        )
