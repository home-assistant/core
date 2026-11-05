"""Test AI task platform of the LiteLLM integration."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx2
from openai import APIConnectionError
from openai.types.decision import Decision
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components import ai_task, media_source
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_MODEL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration

DECISION_MODEL = "decision-model"

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
ANSWERS = [
    {"type": "predicate", "name": "delivered", "probability": 0.97},
    {
        "type": "choice",
        "name": "location",
        "choice": "door",
        "probabilities": [
            {"value": "door", "probability": 0.9},
            {"value": "other", "probability": 0.1},
        ],
        "confidence": 0.5,
    },
    {
        "type": "score",
        "name": "attention",
        "score": 0.15,
        "probabilities": [
            {"value": 2, "label": "2", "probability": 0.05},
            {"value": 0, "label": "0", "probability": 0.9},
            {"value": 1, "label": "1", "probability": 0.05},
        ],
        "confidence": 0.5,
    },
]


def decision(answers: list[dict]) -> Decision:
    """Build a response using the SDK's actual response types."""
    return Decision.model_validate(
        {
            "model": DECISION_MODEL,
            "answers": answers,
            "usage": {
                "input_tokens": 10,
                "output_tokens": 0,
                "total_tokens": 10,
                "input_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 0},
                "output_tokens_details": {"reasoning_tokens": 0},
            },
        }
    )


@pytest.fixture
def mock_decisions(mock_openai_client: AsyncMock) -> AsyncMock:
    """Mock the decisions endpoint of the client."""
    mock = AsyncMock(return_value=decision(ANSWERS))
    mock_openai_client.decisions.create = mock
    return mock


@pytest.fixture
async def evaluation_entity(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openai_client: AsyncMock,
    mock_models: AsyncMock,
    mock_decisions: AsyncMock,
) -> str:
    """Create an evaluation entity through the subentry flow."""
    await setup_integration(hass, mock_config_entry)

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "ai_task_evaluate"),
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_MODEL: DECISION_MODEL}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == DECISION_MODEL
    assert result["data"] == {CONF_MODEL: DECISION_MODEL}
    await hass.async_block_till_done()
    return "ai_task.decision_model"


async def test_evaluate(
    hass: HomeAssistant,
    evaluation_entity: str,
    mock_decisions: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Translate all question types and reorder score probabilities by index."""
    result = await ai_task.async_evaluate(
        hass,
        task_name="Delivery",
        entity_id=evaluation_entity,
        state={"message": "Delivered"},
        questions=QUESTIONS,
    )
    assert result.answers == {
        "delivered": ai_task.NoulAnswer(noul=0.97),
        "location": ai_task.ChoiceAnswer(
            choice="door", probabilities={"door": 0.9, "other": 0.1}
        ),
        "attention": ai_task.ScoreAnswer(score=0.15, probabilities=[0.9, 0.05, 0.05]),
    }
    assert mock_decisions.call_args.kwargs == {
        "model": DECISION_MODEL,
        "input": '{"message":"Delivered"}',
        "questions": [
            {
                "type": "predicate",
                "name": "delivered",
                "instructions": "Has the package arrived?",
            },
            {
                "type": "choice",
                "name": "location",
                "instructions": "Where was it left?",
                "choices": [
                    {"value": "door", "description": "At the door"},
                    {"value": "other", "description": "Somewhere else"},
                ],
            },
            {
                "type": "score",
                "name": "attention",
                "instructions": "How urgent is it?",
                "levels": [
                    {"label": "0", "description": "No action"},
                    {"label": "1", "description": "Action needed"},
                    {"label": "2", "description": "Action needed today"},
                ],
            },
        ],
    }
    entity = entity_registry.async_get(evaluation_entity)
    assert entity is not None
    assert (
        mock_config_entry.subentries[entity.config_subentry_id].subentry_type
        == "ai_task_evaluate"
    )
    assert hass.states.get(evaluation_entity).attributes["supported_features"] == (
        ai_task.AITaskEntityFeature.EVALUATE
        | ai_task.AITaskEntityFeature.SUPPORT_ATTACHMENTS
    )


async def test_images(
    hass: HomeAssistant,
    evaluation_entity: str,
    mock_decisions: AsyncMock,
    tmp_path: Path,
) -> None:
    """Pass resolved image bytes with optional textual context."""
    image_path = tmp_path / "snapshot.jpg"
    image_path.write_bytes(b"camera image")
    with patch(
        "homeassistant.components.media_source.async_resolve_media",
        return_value=media_source.PlayMedia(
            url="/media/snapshot.jpg",
            mime_type="image/jpeg",
            path=image_path,
        ),
    ):
        await ai_task.async_evaluate(
            hass,
            task_name="Delivery",
            entity_id=evaluation_entity,
            state="Look at the front door",
            questions=QUESTIONS,
            attachments=[
                {
                    "media_content_id": "media-source://media_source/local/snapshot.jpg",
                    "media_content_type": "image/jpeg",
                }
            ],
        )
    assert mock_decisions.call_args.kwargs["input"] == [
        {
            "role": "user",
            "content": [
                {"type": "input_text", "text": "Look at the front door"},
                {
                    "type": "input_image",
                    "image_url": "data:image/jpeg;base64,Y2FtZXJhIGltYWdl",
                },
            ],
        }
    ]


async def test_unsupported_attachment(
    hass: HomeAssistant,
    evaluation_entity: str,
    mock_decisions: AsyncMock,
    tmp_path: Path,
) -> None:
    """Reject non-image attachments instead of ignoring them."""
    with (
        patch(
            "homeassistant.components.media_source.async_resolve_media",
            return_value=media_source.PlayMedia(
                url="/media/audio.wav",
                mime_type="audio/wav",
                path=tmp_path / "audio.wav",
            ),
        ),
        pytest.raises(
            HomeAssistantError,
            match="only support JPEG, PNG, WebP, and GIF image attachments; received audio/wav",
        ),
    ):
        await ai_task.async_evaluate(
            hass,
            task_name="Delivery",
            entity_id=evaluation_entity,
            questions=QUESTIONS,
            attachments=[
                {
                    "media_content_id": "media-source://media_source/local/audio.wav",
                    "media_content_type": "audio/wav",
                }
            ],
        )
    mock_decisions.assert_not_called()


@pytest.mark.parametrize(
    ("answers", "error"),
    [
        pytest.param([{**ANSWERS[0], "name": None}], "unnamed answer", id="unnamed"),
        pytest.param(
            [{**ANSWERS[0], "name": "unknown"}],
            "unexpected question name",
            id="unknown-name",
        ),
        pytest.param(
            [ANSWERS[0], ANSWERS[0]], "unexpected question name", id="duplicate-name"
        ),
        pytest.param(
            [{"type": "refusal", "name": "delivered"}],
            "refused evaluation question delivered",
            id="refusal",
        ),
        pytest.param(
            [ANSWERS[0], {**ANSWERS[1], "choice": True}],
            "invalid choice",
            id="boolean-choice",
        ),
        pytest.param(
            [
                ANSWERS[0],
                {**ANSWERS[1], "probabilities": [ANSWERS[1]["probabilities"][0]] * 2},
            ],
            "duplicate choice probabilities",
            id="duplicate-probability",
        ),
        pytest.param(
            [
                ANSWERS[0],
                ANSWERS[1],
                {**ANSWERS[2], "probabilities": [ANSWERS[2]["probabilities"][0]] * 3},
            ],
            "invalid score levels",
            id="duplicate-level",
        ),
    ],
)
async def test_invalid_responses(
    hass: HomeAssistant,
    evaluation_entity: str,
    mock_decisions: AsyncMock,
    answers: list[dict],
    error: str,
) -> None:
    """Handle refusals and malformed provider responses as action errors."""
    mock_decisions.return_value = decision(answers)
    with pytest.raises(HomeAssistantError, match=error):
        await ai_task.async_evaluate(
            hass,
            task_name="Delivery",
            entity_id=evaluation_entity,
            state="Delivered",
            questions=QUESTIONS,
        )


async def test_api_error(
    hass: HomeAssistant, evaluation_entity: str, mock_decisions: AsyncMock
) -> None:
    """Translate SDK errors into Home Assistant errors."""
    mock_decisions.side_effect = APIConnectionError(
        request=httpx2.Request("POST", "http://localhost:4000/v1/decisions")
    )
    with pytest.raises(HomeAssistantError, match="Error evaluating LiteLLM task"):
        await ai_task.async_evaluate(
            hass,
            task_name="Delivery",
            entity_id=evaluation_entity,
            state="Delivered",
            questions=QUESTIONS,
        )
