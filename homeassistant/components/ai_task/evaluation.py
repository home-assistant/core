"""Types and validation for decision tasks."""

from dataclasses import dataclass
import json
import math
from typing import Any, Literal, TypedDict

import probatio

from homeassistant.components.conversation import Attachment
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util.json import JsonValueType


class NoulQuestion(TypedDict):
    """A question estimating the probability of yes."""

    type: Literal["noul"]
    instructions: str


class ChoiceQuestion(TypedDict):
    """A question selecting among named alternatives."""

    type: Literal["choice"]
    instructions: str
    criteria: dict[str, str]


class ScoreQuestion(TypedDict):
    """A question assessing ordered levels."""

    type: Literal["score"]
    instructions: str
    criteria: list[str]


type EvaluationQuestion = NoulQuestion | ChoiceQuestion | ScoreQuestion


class NoulAnswer(TypedDict):
    """The estimated probability of yes."""

    type: Literal["noul"]
    noul: float


class ChoiceAnswer(TypedDict):
    """A selected alternative and its distribution."""

    type: Literal["choice"]
    choice: str
    probabilities: dict[str, float]


class ScoreAnswer(TypedDict):
    """An expected level index and its distribution."""

    type: Literal["score"]
    score: float
    probabilities: list[float]


type EvaluationAnswer = NoulAnswer | ChoiceAnswer | ScoreAnswer

_NONEMPTY_STRING = probatio.All(str, probatio.Length(min=1))
QUESTIONS_SCHEMA = probatio.Schema(
    probatio.All(
        {
            _NONEMPTY_STRING: probatio.Any(
                {
                    probatio.Required("type"): "noul",
                    probatio.Required("instructions"): _NONEMPTY_STRING,
                },
                {
                    probatio.Required("type"): "choice",
                    probatio.Required("instructions"): _NONEMPTY_STRING,
                    probatio.Required("criteria"): probatio.All(
                        {_NONEMPTY_STRING: str}, probatio.Length(min=2)
                    ),
                },
                {
                    probatio.Required("type"): "score",
                    probatio.Required("instructions"): _NONEMPTY_STRING,
                    probatio.Required("criteria"): probatio.All(
                        [str], probatio.Length(min=2)
                    ),
                },
            )
        },
        probatio.Length(min=1),
    )
)


def validate_state(value: JsonValueType) -> JsonValueType:
    """Validate that the supplied state is JSON serializable."""
    try:
        json.dumps(value, allow_nan=False)
    except (TypeError, ValueError) as err:
        raise probatio.Invalid("State must be JSON serializable") from err
    return value


@dataclass(slots=True)
class EvaluationTask:
    """Questions to evaluate against shared state and attachments."""

    name: str
    questions: dict[str, EvaluationQuestion]
    state: JsonValueType = None
    attachments: list[Attachment] | None = None


@dataclass(slots=True)
class EvaluationTaskResult:
    """Answers keyed by question ID."""

    answers: dict[str, EvaluationAnswer]

    def as_dict(self) -> dict[str, Any]:
        """Return the action response."""
        return {"answers": self.answers}


def _probability(value: float) -> bool:
    """Return whether a value is a finite probability."""
    return type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 1


def _valid_answer(question: EvaluationQuestion, answer: EvaluationAnswer) -> bool:
    """Validate an answer against its question."""
    if question["type"] == "noul" and answer["type"] == "noul":
        return _probability(answer["noul"])
    if question["type"] == "choice" and answer["type"] == "choice":
        probabilities = answer["probabilities"]
        return (
            probabilities.keys() == question["criteria"].keys()
            and answer["choice"] in probabilities
            and all(_probability(value) for value in probabilities.values())
            and math.isclose(sum(probabilities.values()), 1, abs_tol=1e-6)
            and probabilities[answer["choice"]] == max(probabilities.values())
        )
    if question["type"] == "score" and answer["type"] == "score":
        levels = answer["probabilities"]
        return (
            isinstance(levels, list)
            and len(levels) == len(question["criteria"])
            and all(_probability(value) for value in levels)
            and math.isclose(sum(levels), 1, abs_tol=1e-6)
            and type(answer["score"]) in (int, float)
            and math.isfinite(answer["score"])
            and math.isclose(
                answer["score"],
                sum(index * value for index, value in enumerate(levels)),
                abs_tol=1e-6,
            )
        )
    return False


def validate_result(task: EvaluationTask, result: EvaluationTaskResult) -> None:
    """Reject incomplete or invalid provider results."""
    if result.answers.keys() != task.questions.keys():
        raise HomeAssistantError("Evaluation did not return every requested answer")
    for question_id, question in task.questions.items():
        try:
            valid = _valid_answer(question, result.answers[question_id])
        except KeyError, TypeError, AttributeError:
            valid = False
        if not valid:
            raise HomeAssistantError(f"Invalid evaluation answer for {question_id}")
