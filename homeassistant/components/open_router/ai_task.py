"""AI Task integration for OpenRouter."""

import base64
from json import JSONDecodeError
import logging
from typing import Any, override

import openai
from openai.types.chat import ChatCompletionContentPartParam
from openai.types.shared_params import ResponseFormatJSONSchema
from python_open_router import Modality

from homeassistant.components import ai_task, conversation
from homeassistant.config_entries import ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.json import json_dumps
from homeassistant.util import slugify
from homeassistant.util.json import json_loads

from . import OpenRouterConfigEntry
from .const import CONF_OUTPUT_MODALITIES
from .entity import OpenRouterEntity, async_prepare_files_for_prompt

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: OpenRouterConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up AI Task entities."""
    for subentry in config_entry.subentries.values():
        if subentry.subentry_type == "ai_task_data":
            entity: ai_task.AITaskEntity = OpenRouterAITaskEntity(
                config_entry, subentry
            )
        elif subentry.subentry_type == "ai_task_evaluate":
            entity = OpenRouterEvaluationEntity(config_entry, subentry)
        else:
            continue

        async_add_entities(
            [entity],
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

    @override
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


EVALUATION_PROMPT = (
    "You evaluate questions about the provided state and attachments. "
    "For every question, estimate a calibrated probability for each possible "
    "answer based only on the provided information. Probabilities are numbers "
    "between 0 and 1."
)


def _format_question(question_id: str, question: ai_task.EvaluationQuestion) -> str:
    """Describe a question and the expected answer format for the prompt."""
    lines = [f"Question {question_id}: {question['instructions']}"]
    if question["type"] == "noul":
        lines.append("Answer with the probability that the answer is yes.")
    elif question["type"] == "choice":
        lines.append("Answer with the probability of each option:")
        lines.extend(
            f"- {option}: {description}"
            for option, description in question["criteria"].items()
        )
    else:
        lines.append("Answer with the probability of each level:")
        lines.extend(
            f"- {index}: {description}"
            for index, description in enumerate(question["criteria"])
        )
    return "\n".join(lines)


def _question_schema(question: ai_task.EvaluationQuestion) -> dict[str, Any]:
    """Return the JSON schema for the answer to a question."""
    if question["type"] == "noul":
        return {"type": "number"}
    keys = (
        list(question["criteria"])
        if question["type"] == "choice"
        else [str(index) for index in range(len(question["criteria"]))]
    )
    return {
        "type": "object",
        "properties": {key: {"type": "number"} for key in keys},
        "required": keys,
        "additionalProperties": False,
    }


def _normalize(question_id: str, probabilities: list[Any]) -> list[float]:
    """Validate and normalize a returned probability distribution."""
    if any(
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not 0 <= value <= 1
        for value in probabilities
    ) or not (total := sum(probabilities)):
        raise HomeAssistantError(
            f"OpenRouter returned invalid probabilities for question {question_id}"
        )
    return [value / total for value in probabilities]


def _parse_answer(
    question_id: str, question: ai_task.EvaluationQuestion, value: Any
) -> ai_task.EvaluationAnswer:
    """Convert a structured response value into an evaluation answer."""
    if question["type"] == "noul":
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not 0 <= value <= 1
        ):
            raise HomeAssistantError(
                f"OpenRouter returned an invalid probability for question {question_id}"
            )
        return ai_task.NoulAnswer(noul=float(value))
    if question["type"] == "choice":
        options = list(question["criteria"])
    else:
        options = [str(index) for index in range(len(question["criteria"]))]
    if not isinstance(value, dict) or set(value) != set(options):
        raise HomeAssistantError(
            f"OpenRouter returned invalid probabilities for question {question_id}"
        )
    probabilities = _normalize(question_id, [value[option] for option in options])
    if question["type"] == "choice":
        return ai_task.ChoiceAnswer(
            choice=options[probabilities.index(max(probabilities))],
            probabilities=dict(zip(options, probabilities, strict=True)),
        )
    return ai_task.ScoreAnswer(
        score=sum(index * value for index, value in enumerate(probabilities)),
        probabilities=probabilities,
    )


class OpenRouterEvaluationEntity(ai_task.AITaskEntity, OpenRouterEntity):
    """OpenRouter decision task entity."""

    _attr_name = None
    _attr_supported_features = (
        ai_task.AITaskEntityFeature.EVALUATE
        | ai_task.AITaskEntityFeature.SUPPORT_ATTACHMENTS
    )

    @override
    async def _async_evaluate(
        self, task: ai_task.EvaluationTask
    ) -> ai_task.EvaluationTaskResult:
        """Evaluate questions using structured output."""
        prompt = "\n\n".join(
            _format_question(question_id, question)
            for question_id, question in task.questions.items()
        )
        if task.state is not None:
            state = (
                task.state if isinstance(task.state, str) else json_dumps(task.state)
            )
            prompt += f"\n\nState:\n{state}"

        content: list[ChatCompletionContentPartParam] = [
            {"type": "text", "text": prompt}
        ]
        if task.attachments:
            content.extend(
                await async_prepare_files_for_prompt(
                    self.hass, [(a.path, a.mime_type) for a in task.attachments]
                )
            )

        try:
            response = await self.entry.runtime_data.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": EVALUATION_PROMPT},
                    {"role": "user", "content": content},
                ],
                response_format=ResponseFormatJSONSchema(
                    type="json_schema",
                    json_schema={
                        "name": slugify(task.name)[:64] or "evaluation",
                        "strict": True,
                        "schema": {
                            "type": "object",
                            "properties": {
                                question_id: _question_schema(question)
                                for question_id, question in task.questions.items()
                            },
                            "required": list(task.questions),
                            "additionalProperties": False,
                        },
                    },
                ),
                extra_headers={
                    "X-Title": "Home Assistant",
                    "HTTP-Referer": (
                        "https://www.home-assistant.io/integrations/open_router"
                    ),
                },
                extra_body={"provider": {"require_parameters": True}},
            )
        except openai.OpenAIError as err:
            raise HomeAssistantError(
                f"Error evaluating OpenRouter task: {err}"
            ) from err

        if not response.choices or not response.choices[0].message.content:
            raise HomeAssistantError("OpenRouter returned an empty evaluation")
        try:
            data = json_loads(response.choices[0].message.content)
        except JSONDecodeError as err:
            raise HomeAssistantError(
                "Error with OpenRouter structured response"
            ) from err
        if not isinstance(data, dict) or set(data) != set(task.questions):
            raise HomeAssistantError("OpenRouter returned unexpected questions")

        return ai_task.EvaluationTaskResult(
            answers={
                question_id: _parse_answer(question_id, question, data[question_id])
                for question_id, question in task.questions.items()
            }
        )
