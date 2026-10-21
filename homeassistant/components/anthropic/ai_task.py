"""AI Task integration for Anthropic."""

import base64
import io
from json import JSONDecodeError
import logging
from typing import TYPE_CHECKING, Any, override

import anthropic
from anthropic.types import (
    Base64ImageSourceParam,
    CacheControlEphemeralParam,
    ImageBlockParam,
    JSONOutputFormatParam,
    OutputConfigParam,
    TextBlockParam,
)
from anthropic.types.message_create_params import MessageCreateParamsStreaming
from PIL import Image

from homeassistant.components import ai_task, conversation
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.json import json_loads

from .const import (
    CONF_CHAT_MODEL,
    CONF_MAX_TOKENS,
    CONF_PROMPT_CACHING,
    DEFAULT,
    DOMAIN,
    PromptCaching,
)
from .entity import AnthropicBaseLLMEntity, AnthropicDeltaStream

if TYPE_CHECKING:
    from . import AnthropicConfigEntry

PARALLEL_UPDATES = 0

_LOGGER = logging.getLogger(__name__)

# Images per request, fewer for models with a 200k token context window
MAX_IMAGES = 600
MAX_IMAGES_SMALL_CONTEXT = 100
SMALL_CONTEXT_TOKENS = 200_000

# Above this many images in a request, the API limits each side to 2000 px
MANY_IMAGES = 20
MANY_IMAGES_MAX_SIZE = 2000

STOP_REASON_TRANSLATION_KEYS = {
    "refusal": "api_refusal",
    "max_tokens": "response_max_tokens",
    "model_context_window_exceeded": "response_context_window_exceeded",
    "stop_sequence": "response_stop_sequence",
    "pause_turn": "response_incomplete",
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: AnthropicConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up AI Task entities."""
    for subentry in config_entry.subentries.values():
        if subentry.subentry_type != "ai_task_data":
            continue

        async_add_entities(
            [AnthropicTaskEntity(config_entry, subentry)],
            config_subentry_id=subentry.subentry_id,
        )


class AnthropicTaskEntity(
    ai_task.AITaskEntity,
    AnthropicBaseLLMEntity,
):
    """Anthropic AI Task entity."""

    _attr_supported_features = (
        ai_task.AITaskEntityFeature.GENERATE_DATA
        | ai_task.AITaskEntityFeature.CLASSIFY_IMAGE
        | ai_task.AITaskEntityFeature.SUPPORT_ATTACHMENTS
    )
    _attr_translation_key = "ai_task_data"

    @override
    async def _async_generate_data(
        self,
        task: ai_task.GenDataTask,
        chat_log: conversation.ChatLog,
    ) -> ai_task.GenDataTaskResult:
        """Handle a generate data task."""
        await self._async_handle_chat_log(chat_log, task.structure, max_iterations=1000)

        if not isinstance(chat_log.content[-1], conversation.AssistantContent):
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="response_not_found"
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
            # pylint: disable-next=home-assistant-log-and-raise
            _LOGGER.error(
                "Failed to parse JSON response: %s. Response: %s",
                err,
                text,
            )
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="json_parse_error"
            ) from err

        return ai_task.GenDataTaskResult(
            conversation_id=chat_log.conversation_id,
            data=data,
        )

    @override
    async def _async_classify_image(
        self, task: ai_task.ClassifyImageTask
    ) -> ai_task.ClassifyImageResult:
        """Classify an image by the examples of each label."""
        image_count = 1 + sum(len(label.examples) for label in task.labels.values())
        max_images = (
            MAX_IMAGES
            if (self.model_info.max_input_tokens or 0) > SMALL_CONTEXT_TOKENS
            else MAX_IMAGES_SMALL_CONTEXT
        )
        if image_count > max_images:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="too_many_classification_images",
                translation_placeholders={
                    "images": str(image_count),
                    "max_images": str(max_images),
                },
            )
        options: dict[str, Any] = DEFAULT | self.subentry.data
        try:
            content = await self.hass.async_add_executor_job(
                _classification_content,
                task,
                options[CONF_PROMPT_CACHING] != PromptCaching.OFF,
                image_count > MANY_IMAGES,
            )
        except OSError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="classification_image_unreadable",
            ) from err

        question = (
            task.instructions
            or f"{task.name}: Which label matches the image to classify?"
        )
        model_args = MessageCreateParamsStreaming(
            model=options[CONF_CHAT_MODEL],
            max_tokens=options[CONF_MAX_TOKENS],
            system=(
                f"{question} Each label is shown by its examples. Answer with the "
                "label that matches, and set unsure to true when the image to "
                "classify does not clearly match one label."
            ),
            messages=[{"role": "user", "content": content}],
            output_config=OutputConfigParam(
                format=JSONOutputFormatParam(
                    type="json_schema",
                    schema=anthropic.transform_schema(
                        {
                            "type": "object",
                            "properties": {
                                "label": {"type": "string", "enum": [*task.labels]},
                                "unsure": {"type": "boolean"},
                            },
                            "required": ["label", "unsure"],
                        }
                    ),
                )
            ),
            stream=True,
        )

        coordinator = self.entry.runtime_data
        text = ""
        try:
            stream = await coordinator.client.messages.create(**model_args)
            delta_stream = AnthropicDeltaStream(stream)
            async with stream:
                async for delta in delta_stream:
                    if isinstance(part := delta.get("content"), str):
                        text += part
        except anthropic.AuthenticationError as err:
            # Let the coordinator confirm the failure and start reauthentication
            await coordinator.async_request_refresh()
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="api_authentication_error",
                translation_placeholders={"message": err.message},
            ) from err
        except anthropic.APIConnectionError as err:
            coordinator.mark_connection_error()
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="api_error",
                translation_placeholders={"message": err.message},
            ) from err
        except anthropic.AnthropicError as err:
            coordinator.mark_connection_healthy()
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="api_error",
                translation_placeholders={
                    "message": err.message
                    if isinstance(err, anthropic.APIError)
                    else str(err)
                },
            ) from err
        coordinator.mark_connection_healthy()

        if (stop_reason := delta_stream.stop_reason) in STOP_REASON_TRANSLATION_KEYS:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key=STOP_REASON_TRANSLATION_KEYS[stop_reason],
            )
        try:
            data = json_loads(text)
        except JSONDecodeError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="json_parse_error"
            ) from err
        if not isinstance(data, dict) or not isinstance(
            unsure := data.get("unsure"), bool
        ):
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="classification_not_found"
            )
        if unsure:
            return ai_task.ClassifyImageResult(label=None)
        if not isinstance(label := data.get("label"), str) or label not in task.labels:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="classification_not_found"
            )
        return ai_task.ClassifyImageResult(label=label)


def _classification_content(
    task: ai_task.ClassifyImageTask, cache_examples: bool, shrink: bool
) -> list[TextBlockParam | ImageBlockParam]:
    """Build the examples of each label and the image to classify; blocking I/O."""

    def image_block(attachment: conversation.Attachment) -> ImageBlockParam:
        data = ai_task.crop_image(attachment.path, task.region)
        if shrink:
            data = _shrink_jpeg(data, MANY_IMAGES_MAX_SIZE)
        return ImageBlockParam(
            type="image",
            source=Base64ImageSourceParam(
                type="base64",
                media_type="image/jpeg",
                data=base64.b64encode(data).decode("ascii"),
            ),
        )

    content: list[TextBlockParam | ImageBlockParam] = []
    for label_id, label in task.labels.items():
        text = f'Examples of "{label_id}"'
        if label.description is not None:
            text = f"{text}: {label.description}"
        content.append(TextBlockParam(type="text", text=text))
        content.extend(image_block(example) for example in label.examples)
    if cache_examples:
        # The examples stay the same between calls, only the image changes
        content[-1]["cache_control"] = CacheControlEphemeralParam(type="ephemeral")
    content.append(TextBlockParam(type="text", text="Image to classify:"))
    content.append(image_block(task.image))
    return content


def _shrink_jpeg(data: bytes, max_size: int) -> bytes:
    """Fit a JPEG image into a square of the given size; blocking."""
    with Image.open(io.BytesIO(data)) as image:
        if max(image.size) <= max_size:
            return data
        image.thumbnail((max_size, max_size))
        output = io.BytesIO()
        image.save(output, format="JPEG", quality=95)
    return output.getvalue()
