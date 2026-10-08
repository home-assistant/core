"""Test decision tasks and their result contract."""

from collections.abc import Callable, Generator
from datetime import timedelta
from functools import partial
import math
from pathlib import Path
from unittest.mock import AsyncMock, patch

import probatio
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components import ai_task
from homeassistant.components.ai_task.const import DATA_PREFERENCES
from homeassistant.components.camera import Image
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import chat_session
from homeassistant.util import dt as dt_util
from homeassistant.util.json import JsonValueType

from .conftest import TEST_ENTITY_ID, MockAITaskEntity

from tests.common import async_fire_time_changed
from tests.typing import WebSocketGenerator

QUESTIONS: dict[str, ai_task.EvaluationQuestion] = {
    "delivered": {"type": "noul", "instructions": "Has the package arrived?"},
    "location": {
        "type": "choice",
        "instructions": "Where was it left?",
        "criteria": {"door": "At the door", "other": "Somewhere else"},
    },
    "attention": {
        "type": "score",
        "instructions": "How urgent is it?",
        "criteria": ["No action", "Action needed", "Action needed today"],
    },
}
ANSWERS: dict[str, ai_task.EvaluationAnswer] = {
    "delivered": ai_task.NoulAnswer(noul=0.97),
    "location": ai_task.ChoiceAnswer(
        choice="door", probabilities={"door": 0.9, "other": 0.1}
    ),
    "attention": ai_task.ScoreAnswer(score=0.15, probabilities=[0.9, 0.05, 0.05]),
}


@pytest.fixture(autouse=True)
def mock_evaluate(mock_ai_task_entity: MockAITaskEntity) -> Generator[AsyncMock]:
    """Enable evaluation without a generation or conversation dependency."""
    mock_ai_task_entity._attr_supported_features = (
        ai_task.AITaskEntityFeature.EVALUATE
        | ai_task.AITaskEntityFeature.SUPPORT_ATTACHMENTS
    )
    with patch.object(
        mock_ai_task_entity,
        "_async_evaluate",
        return_value=ai_task.EvaluationTaskResult(answers=ANSWERS),
    ) as mock:
        yield mock


@pytest.mark.usefixtures("init_components")
@pytest.mark.parametrize(
    "state",
    [
        pytest.param("Delivered at the door", id="text"),
        pytest.param({"message": "Delivered", "count": 1}, id="object"),
        pytest.param(["Delivered", True], id="array"),
        pytest.param(0, id="zero"),
        pytest.param(False, id="false"),
    ],
)
@pytest.mark.freeze_time("2026-10-08 12:00:00")
async def test_evaluate(
    hass: HomeAssistant,
    mock_evaluate: AsyncMock,
    state: JsonValueType,
    snapshot: SnapshotAssertion,
) -> None:
    """Evaluate mixed questions and preserve state, context, and score ordering."""
    context = Context()
    response = await hass.services.async_call(
        "ai_task",
        "evaluate",
        {
            "task_name": "Delivery",
            "entity_id": TEST_ENTITY_ID,
            "state": state,
            "questions": QUESTIONS,
        },
        blocking=True,
        return_response=True,
        context=context,
    )
    assert response == snapshot
    task = mock_evaluate.call_args.args[0]
    assert task.state == state
    assert task.questions == QUESTIONS
    assert task.name == "Delivery"
    assert task.attachments is None
    entity_state = hass.states.get(TEST_ENTITY_ID)
    assert entity_state.context is context
    assert entity_state.state == "2026-10-08T12:00:00+00:00"


@pytest.mark.usefixtures("init_components")
async def test_preferences(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Set and clear the preferred evaluation entity through the public API."""
    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {"type": "ai_task/preferences/set", "evaluate_entity_id": TEST_ENTITY_ID}
    )
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"]["evaluate_entity_id"] == TEST_ENTITY_ID
    result = await ai_task.async_evaluate(
        hass, task_name="Delivery", state="Delivered", questions=QUESTIONS
    )
    assert result.answers == ANSWERS
    await client.send_json_auto_id(
        {"type": "ai_task/preferences/set", "evaluate_entity_id": None}
    )
    msg = await client.receive_json()
    assert msg["success"]
    assert hass.data[DATA_PREFERENCES].evaluate_entity_id is None


@pytest.mark.usefixtures("init_components")
@pytest.mark.parametrize(
    ("entity_id", "error"),
    [
        pytest.param(None, "No entity_id", id="no-preference"),
        pytest.param("ai_task.unknown", "not found", id="unknown-entity"),
    ],
)
async def test_missing_entity(
    hass: HomeAssistant, entity_id: str | None, error: str
) -> None:
    """Report missing entities or preferences."""
    with pytest.raises(HomeAssistantError, match=error):
        await ai_task.async_evaluate(
            hass,
            task_name="Delivery",
            entity_id=entity_id,
            state="Delivered",
            questions=QUESTIONS,
        )


@pytest.mark.usefixtures("init_components")
@pytest.mark.parametrize(
    ("features", "attachments", "error"),
    [
        pytest.param(
            ai_task.AITaskEntityFeature.GENERATE_DATA
            | ai_task.AITaskEntityFeature.SUPPORT_ATTACHMENTS,
            [],
            "does not support evaluation",
            id="no-evaluation",
        ),
        pytest.param(
            ai_task.AITaskEntityFeature.EVALUATE,
            [
                {
                    "media_content_id": "media-source://camera/camera.front_door",
                    "media_content_type": "image/jpeg",
                }
            ],
            "does not support attachments",
            id="no-attachments",
        ),
    ],
)
async def test_features(
    hass: HomeAssistant,
    mock_ai_task_entity: MockAITaskEntity,
    features: ai_task.AITaskEntityFeature,
    attachments: list[dict[str, str]],
    error: str,
    mock_evaluate: AsyncMock,
) -> None:
    """Require evaluation support and the shared attachment capability."""
    mock_ai_task_entity.supported_features = features
    with pytest.raises(HomeAssistantError, match=error):
        await ai_task.async_evaluate(
            hass,
            task_name="Delivery",
            entity_id=TEST_ENTITY_ID,
            state="Delivered",
            questions=QUESTIONS,
            attachments=attachments,
        )
    mock_evaluate.assert_not_called()


@pytest.mark.usefixtures("init_components")
async def test_camera_only(hass: HomeAssistant, mock_evaluate: AsyncMock) -> None:
    """Resolve a camera once and clean its temporary file after evaluation."""
    captured_paths: list[Path] = []

    async def evaluate(task: ai_task.EvaluationTask) -> ai_task.EvaluationTaskResult:
        assert task.state is None
        assert len(task.attachments) == 1
        attachment = task.attachments[0]
        assert attachment.mime_type == "image/jpeg"
        assert (
            await hass.async_add_executor_job(attachment.path.read_bytes)
            == b"camera image"
        )
        captured_paths.append(attachment.path)
        return ai_task.EvaluationTaskResult(answers=ANSWERS)

    mock_evaluate.side_effect = evaluate
    with patch(
        "homeassistant.components.camera.async_get_image",
        return_value=Image("image/jpeg", b"camera image"),
    ) as get_image:
        await hass.services.async_call(
            "ai_task",
            "evaluate",
            {
                "task_name": "Delivery",
                "entity_id": TEST_ENTITY_ID,
                "questions": QUESTIONS,
                "attachments": [
                    {
                        "media_content_id": "media-source://camera/camera.front_door",
                        "media_content_type": "image/jpeg",
                    }
                ],
            },
            blocking=True,
            return_response=True,
        )
    get_image.assert_awaited_once()
    async_fire_time_changed(
        hass,
        dt_util.utcnow() + chat_session.CONVERSATION_TIMEOUT + timedelta(seconds=1),
    )
    await hass.async_block_till_done()
    assert len(captured_paths) == 1
    assert not captured_paths[0].exists()


@pytest.mark.usefixtures("init_components")
async def test_missing_input(hass: HomeAssistant, mock_evaluate: AsyncMock) -> None:
    """Reject a task with neither state nor attachments."""
    with pytest.raises(HomeAssistantError, match="requires state or attachments"):
        await ai_task.async_evaluate(
            hass, task_name="Delivery", entity_id=TEST_ENTITY_ID, questions=QUESTIONS
        )
    mock_evaluate.assert_not_called()


@pytest.mark.usefixtures("init_components")
@pytest.mark.parametrize(
    "questions",
    [
        pytest.param({}, id="empty"),
        pytest.param(
            {"q": {"type": "unknown", "instructions": "Question"}}, id="unknown-type"
        ),
        pytest.param({"q": {"type": "noul"}}, id="missing-instructions"),
        pytest.param(
            {"q": {"type": "noul", "instructions": ""}}, id="empty-instructions"
        ),
        pytest.param(
            {
                "q": {
                    "type": "choice",
                    "instructions": "Question",
                    "criteria": {"only": "One"},
                }
            },
            id="one-choice",
        ),
        pytest.param(
            {"q": {"type": "score", "instructions": "Question", "criteria": ["only"]}},
            id="one-level",
        ),
        pytest.param(
            {"q": {"type": "noul", "instructions": "Question", "criteria": []}},
            id="extra-field",
        ),
        pytest.param({"": {"type": "noul", "instructions": "Question"}}, id="empty-id"),
    ],
)
async def test_invalid_questions(
    hass: HomeAssistant, questions: dict, mock_evaluate: AsyncMock
) -> None:
    """Validate questions before calling a provider, including Python callers."""
    with pytest.raises(probatio.Invalid):
        await ai_task.async_evaluate(
            hass,
            task_name="Invalid",
            entity_id=TEST_ENTITY_ID,
            state="State",
            questions=questions,
        )
    mock_evaluate.assert_not_called()


@pytest.mark.usefixtures("init_components")
@pytest.mark.parametrize(
    "state",
    [
        pytest.param(math.nan, id="nan"),
        pytest.param({"value": math.inf}, id="infinity"),
        pytest.param({"value": object()}, id="non-json-object"),
    ],
)
async def test_invalid_state(
    hass: HomeAssistant, state: JsonValueType, mock_evaluate: AsyncMock
) -> None:
    """Reject state that cannot be represented as JSON."""
    with pytest.raises(probatio.Invalid, match="JSON serializable"):
        await ai_task.async_evaluate(
            hass,
            task_name="Invalid",
            entity_id=TEST_ENTITY_ID,
            state=state,
            questions=QUESTIONS,
        )
    mock_evaluate.assert_not_called()


@pytest.mark.parametrize(
    "create_answer",
    [
        pytest.param(partial(ai_task.NoulAnswer, noul=math.nan), id="nan"),
        pytest.param(partial(ai_task.NoulAnswer, noul=math.inf), id="infinity"),
        pytest.param(partial(ai_task.NoulAnswer, noul=-0.1), id="negative"),
        pytest.param(partial(ai_task.NoulAnswer, noul=1.1), id="above-one"),
        pytest.param(partial(ai_task.NoulAnswer, noul=True), id="boolean"),
        pytest.param(
            partial(
                ai_task.ChoiceAnswer,
                choice="other",
                probabilities={"door": 0.9, "other": 0.1},
            ),
            id="not-argmax",
        ),
        pytest.param(
            partial(
                ai_task.ChoiceAnswer,
                choice="missing",
                probabilities={"door": 0.9, "other": 0.1},
            ),
            id="unknown-choice",
        ),
        pytest.param(
            partial(
                ai_task.ChoiceAnswer,
                choice="door",
                probabilities={"door": 0.9, "other": 0.9},
            ),
            id="unnormalized-choice",
        ),
        pytest.param(
            partial(
                ai_task.ChoiceAnswer,
                choice="door",
                probabilities={"door": math.nan, "other": 0.1},
            ),
            id="nonfinite-choice",
        ),
        pytest.param(
            partial(ai_task.ScoreAnswer, score=0.2, probabilities=[0.9, 0.05, 0.05]),
            id="incorrect-expectation",
        ),
        pytest.param(
            partial(
                ai_task.ScoreAnswer, score=0, probabilities={"0": 1, "1": 0, "2": 0}
            ),
            id="mapping-not-list",
        ),
        pytest.param(
            partial(ai_task.ScoreAnswer, score=0, probabilities=[0.9, 0.9]),
            id="unnormalized-score",
        ),
        pytest.param(
            partial(ai_task.ScoreAnswer, score=0, probabilities=[math.inf, 0]),
            id="nonfinite-score-probability",
        ),
        pytest.param(
            partial(ai_task.ScoreAnswer, score=math.nan, probabilities=[1, 0]),
            id="nonfinite-score",
        ),
    ],
)
def test_invalid_answer_values(
    create_answer: Callable[[], ai_task.EvaluationAnswer],
) -> None:
    """Reject invalid answer values when constructing the dataclass."""
    with pytest.raises(HomeAssistantError, match="Invalid .* answer"):
        create_answer()


@pytest.mark.parametrize(
    "answers",
    [
        pytest.param(None, id="none"),
        pytest.param([], id="list"),
        pytest.param(
            {"delivered": {"type": "noul", "noul": 0.5}}, id="dictionary-not-dataclass"
        ),
    ],
)
def test_invalid_result(answers: dict[str, ai_task.EvaluationAnswer]) -> None:
    """Require answer dataclasses when constructing the task result."""
    with pytest.raises(HomeAssistantError, match="Invalid evaluation answers"):
        ai_task.EvaluationTaskResult(answers=answers)
