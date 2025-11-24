"""AI Task integration for Home Assistant Cloud."""

from __future__ import annotations

from collections.abc import Iterable
from json import JSONDecodeError
import logging
from typing import Any

from hass_nabucasa import Cloud
from hass_nabucasa.llm import (
    LLMAuthenticationError,
    LLMError,
    LLMImageAttachment,
    LLMRateLimitError,
    LLMResponseError,
    LLMServiceError,
)
from litellm import BaseResponsesAPIStreamingIterator, ResponsesAPIResponse
import voluptuous as vol
from voluptuous_openapi import convert

from homeassistant.components import ai_task, conversation
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers import llm
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import slugify
from homeassistant.util.json import json_loads

from .client import CloudClient
from .const import AI_TASK_ENTITY_UNIQUE_ID, DATA_CLOUD
from .helpers import LLMChatHelper, LLMFileHelper

_LOGGER = logging.getLogger(__name__)


def _ensure_schema_constraints(schema: dict[str, Any]) -> None:
    """Ensure generated schemas match the Responses API expectations."""
    schema_type = schema.get("type")

    if schema_type == "object":
        schema.setdefault("additionalProperties", False)
        properties = schema.get("properties")
        if isinstance(properties, dict):
            for property_schema in properties.values():
                if isinstance(property_schema, dict):
                    _ensure_schema_constraints(property_schema)
    elif schema_type == "array":
        items = schema.get("items")
        if isinstance(items, dict):
            _ensure_schema_constraints(items)


def _format_structured_output(
    structure: vol.Schema, llm_api: llm.APIInstance | None
) -> dict[str, Any]:
    """Format structured output for OpenAI format."""
    schema: dict[str, Any] = convert(
        structure,
        custom_serializer=(
            llm_api.custom_serializer if llm_api else llm.selector_serializer
        ),
    )
    _ensure_schema_constraints(schema)
    return schema


def _flatten_text_value(text: Any) -> str | None:
    """Normalize text payloads from OpenAI Responses API objects."""
    if isinstance(text, str):
        return text

    if isinstance(text, Iterable):
        parts: list[str] = []
        for entry in text:
            if isinstance(entry, str):
                parts.append(entry)
            elif isinstance(entry, dict):
                value = entry.get("text")
                if isinstance(value, str):
                    parts.append(value)
            else:
                value = getattr(entry, "text", None)
                if isinstance(value, str):
                    parts.append(value)
        if parts:
            return "".join(parts)

    return None


def _extract_text_from_output(output: Any) -> str | None:
    """Extract the first assistant text segment from a Responses output list."""
    if not isinstance(output, Iterable):
        return None

    for item in output:
        if isinstance(item, dict):
            contents = getattr(item, "content", None)
        else:
            contents = getattr(item, "content", None)

        if not contents:
            continue

        for content in contents:
            if isinstance(content, dict):
                text_value = _flatten_text_value(getattr(content, "text", None))
            else:
                text_value = _flatten_text_value(getattr(content, "text", None))

            if text_value:
                return text_value

    return None


def _extract_response_text(
    response: ResponsesAPIResponse | BaseResponsesAPIStreamingIterator,
) -> str:
    """Extract the first text response from a Responses API reply."""
    text_value = _extract_text_from_output(getattr(response, "output", None))
    if text_value:
        return text_value

    if isinstance(response, dict):
        text_value = _extract_text_from_output(response.get("output"))
        if text_value:
            return text_value

    raise TypeError("Unexpected response shape")


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Home Assistant Cloud AI Task entity."""
    cloud = hass.data[DATA_CLOUD]
    try:
        await cloud.llm.async_ensure_token()
    except LLMError:
        return

    async_add_entities([CloudLLMTaskEntity(cloud)])


class CloudLLMTaskEntity(ai_task.AITaskEntity):
    """Home Assistant Cloud AI Task entity."""

    _attr_has_entity_name = True
    _attr_supported_features = (
        ai_task.AITaskEntityFeature.GENERATE_DATA
        | ai_task.AITaskEntityFeature.GENERATE_IMAGE
        | ai_task.AITaskEntityFeature.SUPPORT_ATTACHMENTS
    )
    _attr_translation_key = "cloud_ai"
    _attr_unique_id = AI_TASK_ENTITY_UNIQUE_ID

    def __init__(self, cloud: Cloud[CloudClient]) -> None:
        """Initialize the entity."""
        self._cloud = cloud

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
        response_text: dict[str, Any] | None = None
        if task.structure:
            response_text = {
                "format": {
                    "type": "json_schema",
                    "name": slugify(task.name),
                    "schema": _format_structured_output(
                        task.structure, chat_log.llm_api
                    ),
                    "strict": True,
                }
            }

        response_kwargs = await LLMChatHelper.prepare_chat_for_generation(
            self.hass,
            chat_log,
            response_text,
        )

        try:
            response = await self._cloud.llm.async_generate_data(**response_kwargs)
            content = _extract_response_text(response)

        except LLMAuthenticationError as err:
            raise ConfigEntryAuthFailed("Cloud LLM authentication failed") from err
        except LLMRateLimitError as err:
            raise HomeAssistantError("Cloud LLM is rate limited") from err
        except LLMResponseError as err:
            raise HomeAssistantError(str(err)) from err
        except LLMServiceError as err:
            raise HomeAssistantError("Error talking to Cloud LLM") from err
        except LLMError as err:
            raise HomeAssistantError(str(err)) from err

        if not task.structure:
            return ai_task.GenDataTaskResult(
                conversation_id=chat_log.conversation_id,
                data=content,
            )

        try:
            data = json_loads(content)
        except JSONDecodeError as err:
            _LOGGER.error(
                "Failed to parse JSON response: %s. Response: %s", err, content
            )
            raise HomeAssistantError(
                "Error with Cloud LLM structured response"
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
        attachments: list[LLMImageAttachment] | None = None
        if task.attachments:
            attachments = (
                await LLMFileHelper.async_prepare_image_generation_attachments(
                    self.hass, task.attachments
                )
            )

        try:
            image = await self._cloud.llm.async_generate_image(
                prompt=task.instructions,
                attachments=attachments,
            )
        except LLMAuthenticationError as err:
            raise ConfigEntryAuthFailed("Cloud LLM authentication failed") from err
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
