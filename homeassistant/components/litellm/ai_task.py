"""AI task platform for LiteLLM."""

import base64
from pathlib import Path
from typing import override

import openai
from openai.types.decision import AnswerAnswerResourceChoice
from openai.types.decision_create_params import Question
from openai.types.decision_input_message_param import DecisionInputMessageParam
from openai.types.decision_input_part_union_param import DecisionInputPartUnionParam

from homeassistant.components import ai_task
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.json import json_dumps

from .coordinator import LiteLLMConfigEntry
from .entity import LiteLLMEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LiteLLMConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up AI task entities."""
    for subentry in config_entry.get_subentries_of_type("ai_task_evaluate"):
        async_add_entities(
            [LiteLLMEvaluationEntity(config_entry, subentry)],
            config_subentry_id=subentry.subentry_id,
        )


def _read_image_base64(path: Path) -> str:
    """Read and encode an image off the event loop."""
    return base64.b64encode(path.read_bytes()).decode("ascii")


def _convert_choice(
    answer: AnswerAnswerResourceChoice, options: set[str]
) -> ai_task.ChoiceAnswer:
    """Convert a choice answer, validating it against the requested options."""
    if not isinstance(answer.choice, str) or any(
        not isinstance(option.value, str) for option in answer.probabilities
    ):
        raise HomeAssistantError("LiteLLM returned an invalid choice")
    probabilities = {
        str(option.value): option.probability for option in answer.probabilities
    }
    if set(probabilities) != options:
        raise HomeAssistantError("LiteLLM returned invalid choice probabilities")
    if answer.choice not in options:
        raise HomeAssistantError("LiteLLM returned an unknown choice")
    return ai_task.ChoiceAnswer(choice=answer.choice, probabilities=probabilities)


class LiteLLMEvaluationEntity(LiteLLMEntity, ai_task.AITaskEntity):
    """LiteLLM decision task entity."""

    _attr_name = None
    _attr_supported_features = (
        ai_task.AITaskEntityFeature.EVALUATE
        | ai_task.AITaskEntityFeature.SUPPORT_ATTACHMENTS
    )

    @override
    async def _async_evaluate(
        self, task: ai_task.EvaluationTask
    ) -> ai_task.EvaluationTaskResult:
        """Evaluate questions using the LiteLLM decisions API."""
        questions: list[Question] = []
        score_levels: dict[str, int] = {}
        choice_options: dict[str, set[str]] = {}
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
                choice_options[question_id] = set(question["criteria"])
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
                score_levels[question_id] = len(question["criteria"])
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
                        "LiteLLM decisions only support JPEG, PNG, WebP, and GIF "
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

        coordinator = self.entry.runtime_data
        try:
            response = await coordinator.client.decisions.create(
                model=self.model,
                input=decision_input,
                questions=questions,
            )
        except (openai.AuthenticationError, openai.PermissionDeniedError) as err:
            # Re-check so the proxy is marked unavailable for the auth failure.
            await coordinator.async_request_refresh()
            raise HomeAssistantError(f"Error evaluating LiteLLM task: {err}") from err
        except openai.APIConnectionError as err:
            coordinator.mark_connection_error()
            raise HomeAssistantError(f"Error evaluating LiteLLM task: {err}") from err
        except openai.OpenAIError as err:
            # Reachable but the request failed; keep the entity available.
            coordinator.async_set_updated_data(None)
            raise HomeAssistantError(f"Error evaluating LiteLLM task: {err}") from err
        coordinator.async_set_updated_data(None)

        question_types = {
            question_id: "predicate" if question["type"] == "noul" else question["type"]
            for question_id, question in task.questions.items()
        }
        answers: dict[str, ai_task.EvaluationAnswer] = {}
        for answer in response.answers:
            if answer.name is None:
                raise HomeAssistantError("LiteLLM returned an unnamed answer")
            question_id = answer.name
            if question_id not in task.questions or question_id in answers:
                raise HomeAssistantError("LiteLLM returned an unexpected question name")
            if answer.type == "refusal":
                raise HomeAssistantError(
                    f"LiteLLM refused evaluation question {question_id}"
                )
            if answer.type != question_types[question_id]:
                raise HomeAssistantError("LiteLLM returned an answer of the wrong type")
            if answer.type == "predicate":
                answers[question_id] = ai_task.NoulAnswer(noul=answer.probability)
            elif answer.type == "choice":
                answers[question_id] = _convert_choice(
                    answer, choice_options[question_id]
                )
            elif answer.type == "score":
                levels = sorted(answer.probabilities, key=lambda level: level.value)
                if [level.value for level in levels] != list(
                    range(score_levels[question_id])
                ):
                    raise HomeAssistantError("LiteLLM returned invalid score levels")
                answers[question_id] = ai_task.ScoreAnswer(
                    score=answer.score,
                    probabilities=[level.probability for level in levels],
                )
        if set(answers) != set(task.questions):
            raise HomeAssistantError("LiteLLM did not answer all questions")
        return ai_task.EvaluationTaskResult(answers=answers)
