"""AI task support for LiteLLM."""

import base64
from typing import override

from openai import (
    APIConnectionError,
    AuthenticationError,
    OpenAIError,
    PermissionDeniedError,
)
from openai.types.decision_create_params import Question
from openai.types.decision_input_message_param import DecisionInputMessageParam
from openai.types.decision_input_part_union_param import DecisionInputPartUnionParam

from homeassistant.components import ai_task, conversation
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.json import json_dumps

from .coordinator import LiteLLMConfigEntry
from .entity import LiteLLMEntity

PARALLEL_UPDATES = 0

IMAGE_MIME_TYPES = ("image/png", "image/jpeg", "image/webp", "image/gif")


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LiteLLMConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up LiteLLM AI task entities."""
    for subentry in config_entry.get_subentries_of_type("ai_task_evaluate"):
        async_add_entities(
            [LiteLLMEvaluationEntity(config_entry, subentry)],
            config_subentry_id=subentry.subentry_id,
        )


def _format_question(
    question_id: str, question: ai_task.EvaluationQuestion
) -> Question:
    """Convert an evaluation question to a decisions API question."""
    if question["type"] == "noul":
        return {
            "type": "predicate",
            "name": question_id,
            "instructions": question["instructions"],
        }
    if question["type"] == "choice":
        return {
            "type": "choice",
            "name": question_id,
            "instructions": question["instructions"],
            "choices": [
                {"value": option, "description": description}
                for option, description in question["criteria"].items()
            ],
        }
    return {
        "type": "score",
        "name": question_id,
        "instructions": question["instructions"],
        "levels": [
            {"label": str(index), "description": description}
            for index, description in enumerate(question["criteria"])
        ],
    }


def _read_images(
    attachments: list[conversation.Attachment],
) -> list[DecisionInputPartUnionParam]:
    """Read the image attachments as base64 input parts."""
    content: list[DecisionInputPartUnionParam] = []
    for attachment in attachments:
        mime_type = attachment.mime_type.partition(";")[0].strip().lower()
        if mime_type == "image/jpg":
            mime_type = "image/jpeg"
        if mime_type not in IMAGE_MIME_TYPES:
            raise HomeAssistantError(
                "LiteLLM decisions only support JPEG, PNG, WebP, and GIF "
                f"image attachments; received {attachment.mime_type}"
            )
        try:
            encoded = base64.b64encode(attachment.path.read_bytes()).decode("ascii")
        except OSError as err:
            raise HomeAssistantError("Unable to read evaluation attachment") from err
        content.append(
            {"type": "input_image", "image_url": f"data:{mime_type};base64,{encoded}"}
        )
    return content


class LiteLLMEvaluationEntity(LiteLLMEntity, ai_task.AITaskEntity):
    """LiteLLM AI task evaluation entity."""

    _attr_name = None
    _attr_supported_features = (
        ai_task.AITaskEntityFeature.EVALUATE
        | ai_task.AITaskEntityFeature.SUPPORT_ATTACHMENTS
    )

    @override
    async def _async_evaluate(
        self, task: ai_task.EvaluationTask
    ) -> ai_task.EvaluationTaskResult:
        """Evaluate the questions with the decisions endpoint."""
        state = task.state
        state_text = state if isinstance(state, str) else json_dumps(state)
        decision_input: str | list[DecisionInputMessageParam] = state_text
        if task.attachments:
            content: list[DecisionInputPartUnionParam] = []
            if state is not None:
                content.append({"type": "input_text", "text": state_text})
            content.extend(
                await self.hass.async_add_executor_job(_read_images, task.attachments)
            )
            decision_input = [{"role": "user", "content": content}]

        coordinator = self.entry.runtime_data
        try:
            response = await coordinator.client.decisions.create(
                model=self.model,
                input=decision_input,
                questions=[
                    _format_question(question_id, question)
                    for question_id, question in task.questions.items()
                ],
            )
        except (AuthenticationError, PermissionDeniedError) as err:
            await coordinator.async_request_refresh()
            raise HomeAssistantError(
                f"Authentication error during evaluation: {err}"
            ) from err
        except APIConnectionError as err:
            coordinator.mark_connection_error()
            raise HomeAssistantError(
                f"Connection error during evaluation: {err}"
            ) from err
        except OpenAIError as err:
            coordinator.async_set_updated_data(None)
            raise HomeAssistantError(f"Error during evaluation: {err}") from err
        coordinator.async_set_updated_data(None)

        answers: dict[str, ai_task.EvaluationAnswer] = {}
        for answer in response.answers:
            question_id = answer.name
            if question_id not in task.questions or question_id in answers:
                raise HomeAssistantError(
                    f"LiteLLM returned an unexpected question name: {question_id}"
                )
            if answer.type == "refusal":
                raise HomeAssistantError(
                    f"LiteLLM refused evaluation question {question_id}"
                )
            question = task.questions[question_id]
            if question["type"] == "noul" and answer.type == "predicate":
                answers[question_id] = ai_task.NoulAnswer(noul=answer.probability)
            elif question["type"] == "choice" and answer.type == "choice":
                probabilities = {
                    option.value: option.probability
                    for option in answer.probabilities
                    if isinstance(option.value, str)
                }
                if (
                    not isinstance(answer.choice, str)
                    or answer.choice not in question["criteria"]
                    or len(probabilities) != len(answer.probabilities)
                    or probabilities.keys() != question["criteria"].keys()
                ):
                    raise HomeAssistantError(
                        f"LiteLLM returned an invalid choice for {question_id}"
                    )
                answers[question_id] = ai_task.ChoiceAnswer(
                    choice=answer.choice, probabilities=probabilities
                )
            elif question["type"] == "score" and answer.type == "score":
                levels = sorted(answer.probabilities, key=lambda level: level.value)
                if [level.value for level in levels] != list(
                    range(len(question["criteria"]))
                ):
                    raise HomeAssistantError(
                        f"LiteLLM returned invalid score levels for {question_id}"
                    )
                answers[question_id] = ai_task.ScoreAnswer(
                    score=answer.score,
                    probabilities=[level.probability for level in levels],
                )
            else:
                raise HomeAssistantError(
                    f"LiteLLM returned a {answer.type} answer for "
                    f"{question['type']} question {question_id}"
                )

        # LiteLLM forwards to many backends, and a backend may skip a question
        if missing := task.questions.keys() - answers.keys():
            raise HomeAssistantError(
                f"LiteLLM returned no answer for {', '.join(sorted(missing))}"
            )
        return ai_task.EvaluationTaskResult(answers=answers)
