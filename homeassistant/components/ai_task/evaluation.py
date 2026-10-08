"""Types and validation for decision tasks."""

from dataclasses import asdict, dataclass, field
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


@dataclass(slots=True)
class NoulAnswer:
    """The estimated probability of yes."""

    noul: float
    type: Literal["noul"] = field(default="noul", init=False)


@dataclass(slots=True)
class ChoiceAnswer:
    """A selected alternative and its distribution."""

    choice: str
    probabilities: dict[str, float]
    type: Literal["choice"] = field(default="choice", init=False)


@dataclass(slots=True)
class ScoreAnswer:
    """An expected level index and its distribution."""

    score: float
    probabilities: list[float]
    type: Literal["score"] = field(default="score", init=False)


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
        return asdict(self)


def _probability(value: float) -> bool:
    """Return whether a value is a finite probability."""
    return type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 1


def _valid_answer(question: EvaluationQuestion, answer: EvaluationAnswer) -> bool:
    """Validate an answer against its question."""
    if question["type"] == "noul" and isinstance(answer, NoulAnswer):
        return _probability(answer.noul)
    if question["type"] == "choice" and isinstance(answer, ChoiceAnswer):
        probabilities = answer.probabilities
        return (
            probabilities.keys() == question["criteria"].keys()
            and answer.choice in probabilities
            and all(_probability(value) for value in probabilities.values())
            and math.isclose(sum(probabilities.values()), 1, abs_tol=1e-6)
            and probabilities[answer.choice] == max(probabilities.values())
        )
    if question["type"] == "score" and isinstance(answer, ScoreAnswer):
        levels = answer.probabilities
        return (
            isinstance(levels, list)
            and len(levels) == len(question["criteria"])
            and all(_probability(value) for value in levels)
            and math.isclose(sum(levels), 1, abs_tol=1e-6)
            and type(answer.score) in (int, float)
            and math.isfinite(answer.score)
            and math.isclose(
                answer.score,
                sum(index * value for index, value in enumerate(levels)),
                abs_tol=1e-6,
            )
        )
    return False


def validate_result(task: EvaluationTask, result: EvaluationTaskResult) -> None:
    """Reject incomplete or invalid provider results."""
    if (
        not isinstance(result.answers, dict)
        or result.answers.keys() != task.questions.keys()
    ):
        raise HomeAssistantError("Evaluation did not return every requested answer")
    for question_id, question in task.questions.items():
        try:
            valid = _valid_answer(question, result.answers[question_id])
        except KeyError, TypeError, AttributeError:
            valid = False
        if not valid:
            raise HomeAssistantError(f"Invalid evaluation answer for {question_id}")
