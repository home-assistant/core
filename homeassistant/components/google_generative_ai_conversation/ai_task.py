"""AI Task integration for Google Generative AI Conversation."""

from __future__ import annotations

from json import JSONDecodeError
from typing import TYPE_CHECKING

from google.genai.errors import APIError
from google.genai.types import GenerateContentConfig, Part, PartUnionDict

from homeassistant.components import ai_task, conversation
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.json import json_loads

from .const import CONF_CHAT_MODEL, CONF_RECOMMENDED, LOGGER, RECOMMENDED_IMAGE_MODEL
from .entity import (
    ERROR_GETTING_RESPONSE,
    GoogleGenerativeAILLMBaseEntity,
    async_prepare_files_for_prompt,
)

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigSubentry

    from . import GoogleGenerativeAIConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up AI Task entities."""
    for subentry in config_entry.subentries.values():
        if subentry.subentry_type != "ai_task_data":
            continue

        async_add_entities(
            [GoogleGenerativeAITaskEntity(config_entry, subentry)],
            config_subentry_id=subentry.subentry_id,
        )


class GoogleGenerativeAITaskEntity(
    ai_task.AITaskEntity,
    GoogleGenerativeAILLMBaseEntity,
):
    """Google Generative AI AI Task entity."""

    def __init__(
        self,
        entry: GoogleGenerativeAIConfigEntry,
        subentry: ConfigSubentry,
    ) -> None:
        """Initialize the entity."""
        super().__init__(entry, subentry)
        self._attr_supported_features = (
            ai_task.AITaskEntityFeature.GENERATE_DATA
            | ai_task.AITaskEntityFeature.SUPPORT_ATTACHMENTS
        )

        if subentry.data.get(CONF_RECOMMENDED) or "-image" in subentry.data.get(
            CONF_CHAT_MODEL, ""
        ):
            self._attr_supported_features |= ai_task.AITaskEntityFeature.GENERATE_IMAGE

    async def _async_generate_data(
        self,
        task: ai_task.GenDataTask,
        chat_log: conversation.ChatLog,
    ) -> ai_task.GenDataTaskResult:
        """Handle a generate data task."""
        await self._async_handle_chat_log(chat_log, task.structure)

        if not isinstance(chat_log.content[-1], conversation.AssistantContent):
            LOGGER.error(
                "Last content in chat log is not an AssistantContent: %s. This could be due to the model not returning a valid response",
                chat_log.content[-1],
            )
            raise HomeAssistantError(ERROR_GETTING_RESPONSE)

        text = chat_log.content[-1].content or ""

        if not task.structure:
            return ai_task.GenDataTaskResult(
                conversation_id=chat_log.conversation_id,
                data=text,
            )

        try:
            data = json_loads(text)
        except JSONDecodeError as err:
            LOGGER.error(
                "Failed to parse JSON response: %s. Response: %s",
                err,
                text,
            )
            raise HomeAssistantError(ERROR_GETTING_RESPONSE) from err

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
        # Get the user prompt from the chat log
        user_message = chat_log.content[-1]
        assert isinstance(user_message, conversation.UserContent)

        model = self.subentry.data.get(CONF_CHAT_MODEL, RECOMMENDED_IMAGE_MODEL)
        prompt_parts: list[PartUnionDict] = [user_message.content]
        if user_message.attachments:
            prompt_parts.extend(
                await async_prepare_files_for_prompt(
                    self.hass,
                    self._genai_client,
                    [a.path for a in user_message.attachments],
                )
            )

        try:
            response = await self._genai_client.aio.models.generate_content(
                model=model,
                contents=prompt_parts,
                config=GenerateContentConfig(
                    response_modalities=["TEXT", "IMAGE"],
                ),
            )
        except (APIError, ValueError) as err:
            LOGGER.error("Error generating image: %s", err)
            raise HomeAssistantError(f"Error generating image: {err}") from err

        if response.prompt_feedback:
            raise HomeAssistantError(
                f"Error generating content due to content violations, reason: {response.prompt_feedback.block_reason_message}"
            )

        if (
            not response.candidates
            or not response.candidates[0].content
            or not response.candidates[0].content.parts
        ):
            raise HomeAssistantError("Unknown error generating image")

        # Parse response
        response_text = ""
        response_image: Part | None = None
        for part in response.candidates[0].content.parts:
            if (
                part.inline_data
                and part.inline_data.data
                and part.inline_data.mime_type
                and part.inline_data.mime_type.startswith("image/")
            ):
                if response_image is None:
                    response_image = part
                else:
                    LOGGER.warning("Prompt generated multiple images")
            elif isinstance(part.text, str) and not part.thought:
                response_text += part.text

        if response_image is None:
            raise HomeAssistantError("Response did not include image")

        assert response_image.inline_data is not None
        assert response_image.inline_data.data is not None
        assert response_image.inline_data.mime_type is not None

        image_data = response_image.inline_data.data
        mime_type = response_image.inline_data.mime_type

        chat_log.async_add_assistant_content_without_tools(
            conversation.AssistantContent(
                agent_id=self.entity_id,
                content=response_text,
            )
        )

        return ai_task.GenImageTaskResult(
            image_data=image_data,
            conversation_id=chat_log.conversation_id,
            mime_type=mime_type,
            model=model.partition("/")[-1],
        )
