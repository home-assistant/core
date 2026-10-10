"""Test OpenAI decision tasks."""

from collections.abc import Generator
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx2
from openai import APIConnectionError
from openai.types.decision import Decision
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components import ai_task, camera, media_source
from homeassistant.components.openai_conversation.const import (
    RECOMMENDED_DECISION_MODEL,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.util.json import JsonValueType

from tests.common import MockConfigEntry

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
            "model": RECOMMENDED_DECISION_MODEL,
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
def mock_decisions() -> Generator[AsyncMock]:
    """Mock the Decisions endpoint."""
    with patch(
        "openai.resources.decisions.AsyncDecisions.create",
        return_value=decision(ANSWERS),
    ) as mock:
        yield mock


@pytest.fixture
async def evaluation_entity(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component: None,
    mock_decisions: AsyncMock,
) -> str:
    """Create an evaluation entity through the user flow."""
    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "ai_task_evaluate"),
        context={"source": "user"},
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            "name": "Custom Evaluation",
            "chat_model": RECOMMENDED_DECISION_MODEL,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {"chat_model": RECOMMENDED_DECISION_MODEL}
    await hass.async_block_till_done()
    return "ai_task.custom_evaluation"


@pytest.mark.parametrize(
    "state",
    [
        pytest.param("Delivered", id="text"),
        pytest.param({"message": "Delivered", "count": 2}, id="json"),
    ],
)
async def test_evaluate(
    hass: HomeAssistant,
    evaluation_entity: str,
    mock_decisions: AsyncMock,
    state: JsonValueType,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Translate all question types and reorder score probabilities by index."""
    result = await ai_task.async_evaluate(
        hass,
        task_name="Delivery",
        entity_id=evaluation_entity,
        state=state,
        questions=QUESTIONS,
    )
    assert result.answers == {
        "delivered": ai_task.NoulAnswer(noul=0.97),
        "location": ai_task.ChoiceAnswer(
            choice="door", probabilities={"door": 0.9, "other": 0.1}
        ),
        "attention": ai_task.ScoreAnswer(score=0.15, probabilities=[0.9, 0.05, 0.05]),
    }
    assert result.as_dict() == snapshot
    assert mock_decisions.call_args.kwargs == snapshot
    entity = entity_registry.async_get(evaluation_entity)
    assert (
        mock_config_entry.subentries[entity.config_subentry_id].subentry_type
        == "ai_task_evaluate"
    )
    assert hass.states.get(evaluation_entity).attributes["supported_features"] == (
        ai_task.AITaskEntityFeature.EVALUATE
        | ai_task.AITaskEntityFeature.SUPPORT_ATTACHMENTS
    )


@pytest.mark.parametrize(
    "state",
    [
        pytest.param(None, id="image-only"),
        pytest.param("Look at the front door", id="image-and-state"),
    ],
)
async def test_images(
    hass: HomeAssistant,
    evaluation_entity: str,
    mock_decisions: AsyncMock,
    tmp_path: Path,
    state: JsonValueType,
    snapshot: SnapshotAssertion,
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
            state=state,
            questions=QUESTIONS,
            attachments=[
                {
                    "media_content_id": "media-source://media_source/local/snapshot.jpg",
                    "media_content_type": "image/jpeg",
                }
            ],
        )
    assert mock_decisions.call_args.kwargs["input"] == snapshot


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
        request=httpx2.Request("POST", "https://api.openai.com/v1/decisions")
    )
    with pytest.raises(HomeAssistantError, match="Error evaluating OpenAI task"):
        await ai_task.async_evaluate(
            hass,
            task_name="Delivery",
            entity_id=evaluation_entity,
            state="Delivered",
            questions=QUESTIONS,
        )


async def test_flow_entry_not_loaded(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Require the parent integration to be loaded before adding an entity."""
    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "ai_task_evaluate"),
        context={"source": "user"},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "entry_not_loaded"


async def test_missing_attachment(
    hass: HomeAssistant,
    evaluation_entity: str,
    mock_decisions: AsyncMock,
    tmp_path: Path,
) -> None:
    """Report an unreadable image as an action error."""
    with (
        patch(
            "homeassistant.components.media_source.async_resolve_media",
            return_value=media_source.PlayMedia(
                url="/media/missing.jpg",
                mime_type="image/jpeg",
                path=tmp_path / "missing.jpg",
            ),
        ),
        pytest.raises(HomeAssistantError, match="Unable to read evaluation attachment"),
    ):
        await ai_task.async_evaluate(
            hass,
            task_name="Delivery",
            entity_id=evaluation_entity,
            questions=QUESTIONS,
            attachments=[
                {
                    "media_content_id": "media-source://media_source/local/missing.jpg",
                    "media_content_type": "image/jpeg",
                }
            ],
        )
    mock_decisions.assert_not_called()


async def test_image_limit(
    hass: HomeAssistant,
    evaluation_entity: str,
    mock_decisions: AsyncMock,
) -> None:
    """Reject excessive images before capturing any camera snapshots."""
    with (
        patch("homeassistant.components.camera.async_get_image") as get_image,
        pytest.raises(HomeAssistantError, match="at most 128 attachments"),
    ):
        await ai_task.async_evaluate(
            hass,
            task_name="Delivery",
            entity_id=evaluation_entity,
            questions=QUESTIONS,
            attachments=[
                {"media_content_id": "media-source://camera/camera.front_door"}
            ]
            * 129,
        )
    get_image.assert_not_called()
    mock_decisions.assert_not_called()


@pytest.mark.parametrize(
    "content_type",
    ["image/jpeg", "image/jpg", "IMAGE/JPEG", "image/jpeg; charset=binary"],
)
async def test_camera_snapshot(
    hass: HomeAssistant,
    evaluation_entity: str,
    mock_decisions: AsyncMock,
    content_type: str,
) -> None:
    """Send camera snapshots as images regardless of the camera's stream type."""
    with patch(
        "homeassistant.components.camera.async_get_image",
        return_value=camera.Image(content_type=content_type, content=b"camera image"),
    ) as mock_get_image:
        await hass.services.async_call(
            ai_task.DOMAIN,
            "evaluate",
            {
                "task_name": "Delivery",
                "entity_id": evaluation_entity,
                "questions": QUESTIONS,
                "attachments": [
                    {
                        "media_content_id": "media-source://camera/camera.front_door",
                        "media_content_type": "application/vnd.apple.mpegurl",
                    }
                ],
            },
            blocking=True,
            return_response=True,
        )

    mock_get_image.assert_called_once_with(hass, "camera.front_door")
    assert mock_decisions.call_args.kwargs["input"] == [
        {
            "role": "user",
            "content": [
                {
                    "type": "input_image",
                    "image_url": "data:image/jpeg;base64,Y2FtZXJhIGltYWdl",
                }
            ],
        }
    ]


@pytest.mark.usefixtures("mock_init_component")
async def test_custom_model(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Allow custom decision models when adding an evaluation subentry."""
    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "ai_task_evaluate"), context={"source": "user"}
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"name": "Custom", "chat_model": "custom-decision-model"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {"chat_model": "custom-decision-model"}


@pytest.mark.usefixtures("mock_init_component")
async def test_reconfigure_model(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Change an existing decision model without replacing its subentry."""
    subentry = next(
        entry
        for entry in mock_config_entry.subentries.values()
        if entry.subentry_type == "ai_task_evaluate"
    )
    result = await mock_config_entry.start_subentry_reconfigure_flow(
        hass, subentry.subentry_id
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    schema = result["data_schema"].schema
    assert "name" not in schema
    model_key = next(key for key in schema if key == "chat_model")
    assert model_key.description["suggested_value"] == subentry.data["chat_model"]
    with patch("homeassistant.config_entries.ConfigEntries.async_reload") as reload:
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {"chat_model": "custom-decision-model"}
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    updated = mock_config_entry.subentries[subentry.subentry_id]
    assert updated.title == subentry.title
    assert updated.data["chat_model"] == "custom-decision-model"
    reload.assert_awaited_once_with(mock_config_entry.entry_id)
