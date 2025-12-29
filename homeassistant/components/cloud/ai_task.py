"""AI Task integration for Home Assistant Cloud."""

from __future__ import annotations

import io
from json import JSONDecodeError
import logging

from hass_nabucasa.llm import (
    LLMAuthenticationError,
    LLMError,
    LLMImageAttachment,
    LLMRateLimitError,
    LLMResponseError,
    LLMServiceError,
)
from PIL import Image

from homeassistant.components import ai_task, conversation
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.json import json_loads

from .const import AI_TASK_ENTITY_UNIQUE_ID, DATA_CLOUD
from .entity import BaseCloudLLMEntity

_LOGGER = logging.getLogger(__name__)


def _convert_image_for_editing(data: bytes) -> tuple[bytes, str]:
    """Ensure the image data is in a format accepted by OpenAI image edits."""
    stream = io.BytesIO(data)
    with Image.open(stream) as img:
        mode = img.mode
        if mode not in ("RGBA", "LA", "L"):
            img = img.convert("RGBA")

        output = io.BytesIO()
        if img.mode in ("RGBA", "LA", "L"):
            img.save(output, format="PNG")
            return output.getvalue(), "image/png"

        img.save(output, format=img.format or "PNG")
        return output.getvalue(), f"image/{(img.format or 'png').lower()}"


async def async_prepare_image_generation_attachments(
    hass: HomeAssistant, attachments: list[conversation.Attachment]
) -> list[LLMImageAttachment]:
    """Load attachment data for image generation."""

    def prepare() -> list[LLMImageAttachment]:
        items: list[LLMImageAttachment] = []
        for attachment in attachments:
            if not attachment.mime_type or not attachment.mime_type.startswith(
                "image/"
            ):
                raise HomeAssistantError(
                    "Only image attachments are supported for image generation"
                )
            path = attachment.path
            if not path.exists():
                raise HomeAssistantError(f"`{path}` does not exist")

            data = path.read_bytes()
            mime_type = attachment.mime_type

            try:
                data, mime_type = _convert_image_for_editing(data)
            except HomeAssistantError:
                raise
            except Exception as err:
                raise HomeAssistantError("Failed to process image attachment") from err

            items.append(
                LLMImageAttachment(
                    filename=path.name,
                    mime_type=mime_type,
                    data=data,
                )
            )

        return items

    return await hass.async_add_executor_job(prepare)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Home Assistant Cloud AI Task entity."""
    cloud = hass.data[DATA_CLOUD]
    async_add_entities([CloudAITaskEntity(cloud, config_entry)])


class CloudAITaskEntity(BaseCloudLLMEntity, ai_task.AITaskEntity):
    """Home Assistant Cloud AI Task entity."""

    _attr_has_entity_name = True
    _attr_supported_features = (
        ai_task.AITaskEntityFeature.GENERATE_DATA
        | ai_task.AITaskEntityFeature.GENERATE_IMAGE
        | ai_task.AITaskEntityFeature.SUPPORT_ATTACHMENTS
    )
    _attr_translation_key = "cloud_ai"
    _attr_unique_id = AI_TASK_ENTITY_UNIQUE_ID

    @property
    def available(self) -> bool:
        """Return if the entity is available."""
        return self._cloud.is_logged_in and self._cloud.valid_subscription

    async def _async_generate_data(
        self,
        task: ai_task.GenDataTask,
        chat_log: conversation.ChatLog,
    ) -> ai_task.GenDataTaskResult:
        """Handle a generate data task."""
        await self._async_handle_chat_log(
            "ai_task", chat_log, task.name, task.structure
        )

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
            _LOGGER.error(
                "Failed to parse JSON response: %s. Response: %s",
                err,
                text,
            )
            raise HomeAssistantError("Error with OpenAI structured response") from err

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
        attachments: list[LLMImageAttachment] | None = None
        if task.attachments:
            attachments = await async_prepare_image_generation_attachments(
                self.hass, task.attachments
            )

        try:
            if attachments is None:
                image = await self._cloud.llm.async_generate_image(
                    prompt=task.instructions,
                )
            else:
                image = await self._cloud.llm.async_edit_image(
                    prompt=task.instructions,
                    attachments=attachments,
                )
        except LLMAuthenticationError as err:
            raise HomeAssistantError("Cloud LLM authentication failed") from err
        except LLMRateLimitError as err:
            raise HomeAssistantError("Cloud LLM is rate limited") from err
        except LLMResponseError as err:
            raise HomeAssistantError(str(err)) from err
        except LLMServiceError as err:
            raise HomeAssistantError("Error talking to Cloud LLM") from err
        except LLMError as err:
            raise HomeAssistantError(str(err)) from err

        return ai_task.GenImageTaskResult(
            conversation_id=chat_log.conversation_id,
            mime_type=image["mime_type"],
            image_data=image["image_data"],
            model=image.get("model"),
            width=image.get("width"),
            height=image.get("height"),
            revised_prompt=image.get("revised_prompt"),
        )
