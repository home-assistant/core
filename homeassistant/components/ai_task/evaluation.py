"""Types and validation for decision tasks."""

from dataclasses import asdict, dataclass, field
from typing import Any, Literal, TypedDict

import probatio

from homeassistant.components.conversation import Attachment
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
