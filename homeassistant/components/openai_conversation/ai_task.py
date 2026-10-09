"""AI Task integration for OpenAI."""

import base64
from json import JSONDecodeError
import logging
from pathlib import Path
from typing import TYPE_CHECKING, override

import openai
from openai.types.decision_create_params import Question
from openai.types.decision_input_message_param import DecisionInputMessageParam
from openai.types.decision_input_part_union_param import DecisionInputPartUnionParam
from openai.types.responses.response_output_item import ImageGenerationCall

from homeassistant.components import ai_task, conversation
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.json import json_dumps
from homeassistant.util.json import json_loads

from .const import (
    CONF_CHAT_MODEL,
    CONF_IMAGE_MODEL,
    RECOMMENDED_CHAT_MODEL,
    RECOMMENDED_DECISION_MODEL,
    RECOMMENDED_IMAGE_MODEL,
    UNSUPPORTED_IMAGE_MODELS,
)
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
        if subentry.subentry_type == "ai_task_data":
            entity: ai_task.AITaskEntity = OpenAITaskEntity(config_entry, subentry)
        elif subentry.subentry_type == "ai_task_evaluate":
            entity = OpenAIEvaluationEntity(config_entry, subentry)
        else:
            continue

        async_add_entities(
            [entity],
            config_subentry_id=subentry.subentry_id,
        )


class OpenAITaskEntity(
    ai_task.AITaskEntity,
    OpenAIBaseLLMEntity,
):
    """OpenAI AI Task entity."""

    def __init__(self, entry: OpenAIConfigEntry, subentry: ConfigSubentry) -> None:
        """Initialize the entity."""
        super().__init__(entry, subentry)
        self._attr_supported_features = (
            ai_task.AITaskEntityFeature.GENERATE_DATA
            | ai_task.AITaskEntityFeature.SUPPORT_ATTACHMENTS
        )
        model = self.subentry.data.get(CONF_CHAT_MODEL, RECOMMENDED_CHAT_MODEL)
        if not model.startswith(tuple(UNSUPPORTED_IMAGE_MODELS)):
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
                "Last content in chat log is not an AssistantContent"
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
            raise HomeAssistantError("No image returned")

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


def _read_image_base64(path: Path) -> str:
    """Read and encode an image off the event loop."""
    return base64.b64encode(path.read_bytes()).decode("ascii")


class OpenAIEvaluationEntity(ai_task.AITaskEntity, OpenAIBaseLLMEntity):
    """OpenAI decision task entity."""

    _attr_max_attachments = 128

    _attr_supported_features = (
        ai_task.AITaskEntityFeature.EVALUATE
        | ai_task.AITaskEntityFeature.SUPPORT_ATTACHMENTS
    )

    @override
    async def _async_evaluate(
        self, task: ai_task.EvaluationTask
    ) -> ai_task.EvaluationTaskResult:
        """Evaluate questions using the Decisions API."""
        questions: list[Question] = []
        for question_id, question in task.questions.items():
            if question["type"] == "noul":
                questions.append(
                    {
                        "type": "predicate",
                        "name": question_id,
                        "instructions": question["instructions"],
                    }
                )
            elif question["type"] == "choice":
                questions.append(
                    {
                        "type": "choice",
                        "name": question_id,
                        "instructions": question["instructions"],
                        "choices": [
                            {"value": option, "description": description}
                            for option, description in question["criteria"].items()
                        ],
                    }
                )
            else:
                questions.append(
                    {
                        "type": "score",
                        "name": question_id,
                        "instructions": question["instructions"],
                        "levels": [
                            {"label": str(index), "description": description}
                            for index, description in enumerate(question["criteria"])
                        ],
                    }
                )

        state = task.state
        state_text = state if isinstance(state, str) else json_dumps(state)
        decision_input: str | list[DecisionInputMessageParam] = state_text
        if task.attachments:
            content: list[DecisionInputPartUnionParam] = []
            if state is not None:
                content.append({"type": "input_text", "text": state_text})
            for attachment in task.attachments:
                mime_type = attachment.mime_type.partition(";")[0].strip().lower()
                if mime_type == "image/jpg":
                    mime_type = "image/jpeg"
                if mime_type not in (
                    "image/png",
                    "image/jpeg",
                    "image/webp",
                    "image/gif",
                ):
                    raise HomeAssistantError(
                        "OpenAI decisions only support JPEG, PNG, WebP, and GIF "
                        f"image attachments; received {attachment.mime_type}"
                    )
                try:
                    encoded = await self.hass.async_add_executor_job(
                        _read_image_base64, attachment.path
                    )
                except OSError as err:
                    raise HomeAssistantError(
                        "Unable to read evaluation attachment"
                    ) from err
                content.append(
                    {
                        "type": "input_image",
                        "image_url": f"data:{mime_type};base64,{encoded}",
                    }
                )
            decision_input = [{"role": "user", "content": content}]

        try:
            response = await self.entry.runtime_data.decisions.create(
                model=self.subentry.data.get(
                    CONF_CHAT_MODEL, RECOMMENDED_DECISION_MODEL
                ),
                input=decision_input,
                questions=questions,
            )
        except openai.OpenAIError as err:
            raise HomeAssistantError(f"Error evaluating OpenAI task: {err}") from err

        answers: dict[str, ai_task.EvaluationAnswer] = {}
        for answer in response.answers:
            if answer.name is None:
                raise HomeAssistantError("OpenAI returned an unnamed answer")
            question_id = answer.name
            if question_id not in task.questions or question_id in answers:
                raise HomeAssistantError("OpenAI returned an unexpected question name")
            if answer.type == "refusal":
                raise HomeAssistantError(
                    f"OpenAI refused evaluation question {question_id}"
                )
            if answer.type == "predicate":
                answers[question_id] = ai_task.NoulAnswer(noul=answer.probability)
            elif answer.type == "choice":
                if not isinstance(answer.choice, str) or any(
                    not isinstance(option.value, str) for option in answer.probabilities
                ):
                    raise HomeAssistantError("OpenAI returned an invalid choice")
                probabilities = {
                    str(option.value): option.probability
                    for option in answer.probabilities
                }
                if len(probabilities) != len(answer.probabilities):
                    raise HomeAssistantError(
                        "OpenAI returned duplicate choice probabilities"
                    )
                answers[question_id] = ai_task.ChoiceAnswer(
                    choice=answer.choice, probabilities=probabilities
                )
            elif answer.type == "score":
                levels = sorted(answer.probabilities, key=lambda level: level.value)
                if [level.value for level in levels] != list(range(len(levels))):
                    raise HomeAssistantError("OpenAI returned invalid score levels")
                answers[question_id] = ai_task.ScoreAnswer(
                    score=answer.score,
                    probabilities=[level.probability for level in levels],
                )
            else:
                raise HomeAssistantError("OpenAI returned an unsupported answer type")
        return ai_task.EvaluationTaskResult(answers=answers)
