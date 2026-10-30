"""Test AI Task platform of OpenAI Conversation integration."""

from collections.abc import Generator
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx2
from openai import APIConnectionError, PermissionDeniedError
from openai.types.decision import Decision
import probatio
import pytest
from pytest_homeassistant.common import MockConfigEntry
from syrupy.assertion import SnapshotAssertion

from homeassistant.components import ai_task, media_source
from homeassistant.components.openai_conversation import DOMAIN
from homeassistant.components.openai_conversation.const import (
    CONF_CHAT_MODEL,
    CONF_CODE_INTERPRETER,
    CONF_IMAGE_MODEL,
    CONF_STORE_RESPONSES,
    CONF_VERBOSITY,
    CONF_WEB_SEARCH,
    RECOMMENDED_DECISION_MODEL,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er, issue_registry as ir, selector
from homeassistant.util.json import JsonValueType

from . import create_image_gen_call_item, create_message_item, create_reasoning_item

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


@pytest.mark.usefixtures("mock_init_component")
@pytest.mark.parametrize("expected_store", [False, True])
async def test_generate_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_create_stream: AsyncMock,
    entity_registry: er.EntityRegistry,
    expected_store: bool,
) -> None:
    """Test AI Task data generation."""
    entity_id = "ai_task.openai_ai_task"

    # Ensure entity is linked to the subentry
    entity_entry = entity_registry.async_get(entity_id)
    ai_task_entry = next(
        iter(
            entry
            for entry in mock_config_entry.subentries.values()
            if entry.subentry_type == "ai_task_data"
        )
    )
    hass.config_entries.async_update_subentry(
        mock_config_entry,
        ai_task_entry,
        data={
            **ai_task_entry.data,
            CONF_STORE_RESPONSES: expected_store,
            CONF_WEB_SEARCH: True,
            CONF_CODE_INTERPRETER: True,
        },
    )
    await hass.async_block_till_done()
    assert entity_entry is not None
    assert entity_entry.config_entry_id == mock_config_entry.entry_id
    assert entity_entry.config_subentry_id == ai_task_entry.subentry_id

    # Mock the OpenAI response stream
    mock_create_stream.return_value = [
        create_message_item(id="msg_A", text="The test data", output_index=0)
    ]

    result = await ai_task.async_generate_data(
        hass,
        task_name="Test Task",
        entity_id=entity_id,
        instructions="Generate test data",
    )

    assert result.data == "The test data"
    assert mock_create_stream.call_args is not None
    assert mock_create_stream.call_args.kwargs["store"] is expected_store
    assert mock_create_stream.call_args.kwargs["tools"] == [
        {"type": "web_search", "search_context_size": "medium"},
        {"type": "code_interpreter", "container": {"type": "auto"}},
    ]
    assert (
        mock_create_stream.call_args.kwargs["prompt_cache_key"]
        == ai_task_entry.subentry_id
    )


@pytest.mark.usefixtures("mock_init_component")
@pytest.mark.parametrize(
    ("model", "verbosity", "expected_verbosity"),
    [
        pytest.param("gpt-4o-mini", "low", None, id="without-verbosity"),
        pytest.param("gpt-5-mini", "low", "low", id="low-verbosity"),
        pytest.param("gpt-5-mini", "high", "high", id="high-verbosity"),
    ],
)
async def test_generate_structured_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_create_stream: AsyncMock,
    model: str,
    verbosity: str,
    expected_verbosity: str | None,
) -> None:
    """Test AI Task structured data generation."""
    ai_task_entry = next(
        entry
        for entry in mock_config_entry.subentries.values()
        if entry.subentry_type == "ai_task_data"
    )
    hass.config_entries.async_update_subentry(
        mock_config_entry,
        ai_task_entry,
        data={
            **ai_task_entry.data,
            CONF_CHAT_MODEL: model,
            CONF_VERBOSITY: verbosity,
        },
    )
    await hass.async_block_till_done()

    # Mock the OpenAI response stream with JSON data
    mock_create_stream.return_value = [
        create_message_item(
            id="msg_A", text='{"characters": ["Mario", "Luigi"]}', output_index=0
        )
    ]

    result = await ai_task.async_generate_data(
        hass,
        task_name="Test Task",
        entity_id="ai_task.openai_ai_task",
        instructions="Generate test data",
        structure=probatio.Schema(
            {
                probatio.Required("characters"): selector.selector(
                    {
                        "text": {
                            "multiple": True,
                        }
                    }
                )
            },
        ),
    )

    assert result.data == {"characters": ["Mario", "Luigi"]}
    text = mock_create_stream.call_args.kwargs["text"]
    assert text["format"]["strict"] is True
    assert text.get("verbosity") == expected_verbosity


@pytest.mark.usefixtures("mock_init_component")
async def test_generate_invalid_structured_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_create_stream: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test AI Task with invalid JSON response."""
    # Mock the OpenAI response stream with invalid JSON
    mock_create_stream.return_value = [
        create_message_item(id="msg_A", text="INVALID JSON RESPONSE", output_index=0)
    ]

    with pytest.raises(
        HomeAssistantError, match="Error with OpenAI structured response"
    ):
        await ai_task.async_generate_data(
            hass,
            task_name="Test Task",
            entity_id="ai_task.openai_ai_task",
            instructions="Generate test data",
            structure=probatio.Schema(
                {
                    probatio.Required("characters"): selector.selector(
                        {
                            "text": {
                                "multiple": True,
                            }
                        }
                    )
                },
            ),
        )


@pytest.fixture
def selection_structure() -> probatio.Schema:
    """A multi-select with optional fields represented as null on the wire."""
    return probatio.Schema(
        {
            probatio.Optional("names"): selector.SelectSelector(
                {"options": ["a", "b"], "multiple": True}
            ),
            probatio.Optional("label"): selector.TextSelector(),
        }
    )


@pytest.mark.usefixtures("mock_init_component")
@pytest.mark.parametrize(
    "names",
    [
        pytest.param(["a", "b"], id="selection"),
        pytest.param(["a", "a"], id="duplicates"),
        pytest.param(None, id="omitted"),
    ],
)
async def test_generate_selection(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    mock_create_stream: AsyncMock,
    selection_structure: probatio.Schema,
    names: list[str] | None,
) -> None:
    """Generate multi-select results while accepting duplicates and optional nulls."""
    data = {"names": names, "label": None}
    mock_create_stream.return_value = [
        create_message_item(id="msg_A", text=json.dumps(data), output_index=0)
    ]
    result = await ai_task.async_generate_data(
        hass,
        task_name="Selection",
        entity_id="ai_task.openai_ai_task",
        instructions="Select names",
        structure=selection_structure,
    )
    assert result.data == data
    schema = mock_create_stream.call_args.kwargs["text"]["format"]["schema"]
    assert "uniqueItems" not in schema["properties"]["names"]
    assert (
        "Removed unsupported uniqueItems: true from OpenAI output schema at $.properties.names"
        in caplog.text
    )


@pytest.mark.usefixtures("mock_init_component")
async def test_generate_data_with_attachments(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_create_stream: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test AI Task data generation with attachments."""
    entity_id = "ai_task.openai_ai_task"

    # Mock the OpenAI response stream
    mock_create_stream.return_value = [
        create_message_item(id="msg_A", text="Hi there!", output_index=0)
    ]

    # Test with attachments
    with (
        patch(
            "homeassistant.components.media_source.async_resolve_media",
            side_effect=[
                media_source.PlayMedia(
                    url="http://example.com/doorbell_snapshot.jpg",
                    mime_type="image/jpeg",
                    path=Path("doorbell_snapshot.jpg"),
                ),
                media_source.PlayMedia(
                    url="http://example.com/context.pdf",
                    mime_type="application/pdf",
                    path=Path("context.pdf"),
                ),
            ],
        ),
        patch("pathlib.Path.exists", return_value=True),
        patch(
            "homeassistant.components.openai_conversation.entity.guess_file_type",
            return_value=("image/jpeg", None),
        ),
        patch("pathlib.Path.read_bytes", return_value=b"fake_image_data"),
    ):
        result = await ai_task.async_generate_data(
            hass,
            task_name="Test Task",
            entity_id=entity_id,
            instructions="Test prompt",
            attachments=[
                {"media_content_id": "media-source://media/doorbell_snapshot.jpg"},
                {"media_content_id": "media-source://media/context.pdf"},
            ],
        )

    assert result.data == "Hi there!"

    # Verify that the create stream was called with the correct parameters
    # The last call should have the user message with attachments
    call_args = mock_create_stream.call_args
    assert call_args is not None

    # Check that the input includes the attachments
    input_messages = call_args[1]["input"]
    assert len(input_messages) > 0

    # Find the user message with attachments
    user_message_with_attachments = input_messages[-2]

    assert user_message_with_attachments is not None
    assert isinstance(user_message_with_attachments["content"], list)
    assert len(user_message_with_attachments["content"]) == 3  # Text + attachments
    assert user_message_with_attachments["content"] == [
        {"type": "input_text", "text": "Test prompt"},
        {
            "detail": "auto",
            "image_url": "data:image/jpeg;base64,ZmFrZV9pbWFnZV9kYXRh",
            "type": "input_image",
        },
        {
            "filename": "context.pdf",
            "file_data": "data:application/pdf;base64,ZmFrZV9pbWFnZV9kYXRh",
            "type": "input_file",
        },
    ]


@pytest.mark.usefixtures("mock_init_component")
@pytest.mark.freeze_time("2025-06-14 22:59:00")
@pytest.mark.parametrize("configured_store", [False, True])
@pytest.mark.parametrize(
    ("image_options", "image_model", "input_fidelity_options"),
    [
        ({}, "gpt-image-2.5-flare", {}),
        (
            {CONF_IMAGE_MODEL: "gpt-image-2.5-sunburst"},
            "gpt-image-2.5-sunburst",
            {},
        ),
        (
            {CONF_IMAGE_MODEL: "gpt-image-2.5-flare"},
            "gpt-image-2.5-flare",
            {},
        ),
        ({CONF_IMAGE_MODEL: "gpt-image-2"}, "gpt-image-2", {}),
        (
            {CONF_IMAGE_MODEL: "gpt-image-1.5"},
            "gpt-image-1.5",
            {"input_fidelity": "high"},
        ),
        (
            {CONF_IMAGE_MODEL: "gpt-image-1"},
            "gpt-image-1",
            {"input_fidelity": "high"},
        ),
        ({CONF_IMAGE_MODEL: "gpt-image-1-mini"}, "gpt-image-1-mini", {}),
    ],
)
async def test_generate_image(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_create_stream: AsyncMock,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    image_options: dict[str, str],
    image_model: str,
    input_fidelity_options: dict[str, str],
    configured_store: bool,
) -> None:
    """Test AI Task image generation."""
    entity_id = "ai_task.openai_ai_task"

    # Ensure entity is linked to the subentry
    entity_entry = entity_registry.async_get(entity_id)
    ai_task_entry = next(
        iter(
            entry
            for entry in mock_config_entry.subentries.values()
            if entry.subentry_type == "ai_task_data"
        )
    )
    hass.config_entries.async_update_subentry(
        mock_config_entry,
        ai_task_entry,
        data={
            **ai_task_entry.data,
            **image_options,
            CONF_STORE_RESPONSES: configured_store,
        },
    )
    await hass.async_block_till_done()
    assert entity_entry is not None
    assert entity_entry.config_entry_id == mock_config_entry.entry_id
    assert entity_entry.config_subentry_id == ai_task_entry.subentry_id

    # Mock the OpenAI response stream
    mock_create_stream.return_value = [
        (
            *create_reasoning_item(
                id="rs_A",
                output_index=0,
                reasoning_summary=[["The user asks me to generate an image"]],
            ),
            *create_image_gen_call_item(id="ig_A", output_index=1),
            *create_message_item(id="msg_A", text="", output_index=2),
        )
    ]

    with patch.object(
        media_source.local_source.LocalSource,
        "async_upload_media",
        return_value="media-source://ai_task/image/2025-06-14_155900_test_task.png",
    ) as mock_upload_media:
        result = await ai_task.async_generate_image(
            hass,
            task_name="Test Task",
            entity_id="ai_task.openai_ai_task",
            instructions="Generate test image",
        )

    assert result["height"] == 1024
    assert result["width"] == 1536
    assert result["revised_prompt"] == "Mock revised prompt."
    assert result["mime_type"] == "image/png"
    assert result["model"] == image_model

    mock_upload_media.assert_called_once()
    assert mock_create_stream.call_args is not None
    assert mock_create_stream.call_args.kwargs["store"] is True
    image_tool = next(
        iter(
            tool
            for tool in mock_create_stream.call_args.kwargs["tools"]
            if tool["type"] == "image_generation"
        ),
    )
    assert image_tool == {
        "type": "image_generation",
        "model": image_model,
        "output_format": "png",
        **input_fidelity_options,
    }
    image_data = mock_upload_media.call_args[0][1]
    assert image_data.file.getvalue() == b"A"
    assert image_data.content_type == "image/png"
    assert image_data.filename == "2025-06-14_155900_test_task.png"

    assert (
        issue_registry.async_get_issue(DOMAIN, "organization_verification_required")
        is None
    )


@pytest.mark.usefixtures("mock_init_component")
async def test_repair_issue(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test that repair issue is raised when verification is required."""
    with (
        patch(
            "openai.resources.responses.AsyncResponses.create",
            side_effect=PermissionDeniedError(
                response=httpx2.Response(
                    status_code=403, request=httpx2.Request(method="GET", url="")
                ),
                body=None,
                message="Please click on Verify Organization.",
            ),
        ),
        pytest.raises(HomeAssistantError, match="Error talking to OpenAI"),
    ):
        await ai_task.async_generate_image(
            hass,
            task_name="Test Task",
            entity_id="ai_task.openai_ai_task",
            instructions="Generate test image",
        )

    assert issue_registry.async_get_issue(DOMAIN, "organization_verification_required")


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
        "homeassistant.components.media_source.async_get_media_image",
        return_value=media_source.MediaImage(
            mime_type=content_type, content=b"camera image"
        ),
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

    mock_get_image.assert_called_once_with(
        hass, "media-source://camera/camera.front_door"
    )
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
