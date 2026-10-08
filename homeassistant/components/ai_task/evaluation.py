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

    def __post_init__(self) -> None:
        """Validate the probability."""
        if not _probability(self.noul):
            raise HomeAssistantError("Invalid noul answer")


@dataclass(slots=True)
class ChoiceAnswer:
    """A selected alternative and its distribution."""

    choice: str
    probabilities: dict[str, float]
    type: Literal["choice"] = field(default="choice", init=False)

    def __post_init__(self) -> None:
        """Validate the distribution and selected alternative."""
        if not (
            isinstance(self.probabilities, dict)
            and isinstance(self.choice, str)
            and self.choice in self.probabilities
            and all(_probability(value) for value in self.probabilities.values())
            and math.isclose(sum(self.probabilities.values()), 1, abs_tol=1e-6)
            and self.probabilities[self.choice] == max(self.probabilities.values())
        ):
            raise HomeAssistantError("Invalid choice answer")


@dataclass(slots=True)
class ScoreAnswer:
    """An expected level index and its distribution."""

    score: float
    probabilities: list[float]
    type: Literal["score"] = field(default="score", init=False)

    def __post_init__(self) -> None:
        """Validate the distribution and expected level index."""
        if not (
            isinstance(self.probabilities, list)
            and all(_probability(value) for value in self.probabilities)
            and math.isclose(sum(self.probabilities), 1, abs_tol=1e-6)
            and type(self.score) in (int, float)
            and math.isfinite(self.score)
            and math.isclose(
                self.score,
                sum(index * value for index, value in enumerate(self.probabilities)),
                abs_tol=1e-6,
            )
        ):
            raise HomeAssistantError("Invalid score answer")


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

    def __post_init__(self) -> None:
        """Require typed answers keyed by question ID."""
        if not isinstance(self.answers, dict) or not all(
            isinstance(answer, NoulAnswer | ChoiceAnswer | ScoreAnswer)
            for answer in self.answers.values()
        ):
            raise HomeAssistantError("Invalid evaluation answers")

    def as_dict(self) -> dict[str, Any]:
        """Return the action response."""
        return asdict(self)


def _probability(value: float) -> bool:
    """Return whether a value is a finite probability."""
    return type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 1


def _valid_answer(question: EvaluationQuestion, answer: EvaluationAnswer) -> bool:
    """Validate an answer against its question."""
    if question["type"] == "noul" and isinstance(answer, NoulAnswer):
        return True
    if question["type"] == "choice" and isinstance(answer, ChoiceAnswer):
        return answer.probabilities.keys() == question["criteria"].keys()
    if question["type"] == "score" and isinstance(answer, ScoreAnswer):
        return len(answer.probabilities) == len(question["criteria"])
    return False


def validate_result(task: EvaluationTask, result: EvaluationTaskResult) -> None:
    """Reject incomplete or invalid provider results."""
    if result.answers.keys() != task.questions.keys():
        raise HomeAssistantError("Evaluation did not return every requested answer")
    for question_id, question in task.questions.items():
        if not _valid_answer(question, result.answers[question_id]):
            raise HomeAssistantError(f"Invalid evaluation answer for {question_id}")
