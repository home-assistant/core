"""Test AI task platform of LiteLLM integration."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx2
from openai import APIConnectionError, AuthenticationError, OpenAIError
from openai.types import Decision
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components import ai_task, media_source
from homeassistant.components.litellm.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigSubentryData
from homeassistant.const import CONF_API_KEY, CONF_MODEL, CONF_URL, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import setup_integration
from .conftest import TEST_URL

ENTITY_ID = "ai_task.decider"
QUESTIONS: dict[str, ai_task.EvaluationQuestion] = {
    "delivered": {"type": "noul", "instructions": "Was a package delivered?"},
    "location": {
        "type": "choice",
        "instructions": "Where is the package?",
        "criteria": {"door": "At the front door", "other": "Somewhere else"},
    },
    "attention": {
        "type": "score",
        "instructions": "How urgent is it?",
        "criteria": ["Not urgent", "Somewhat urgent", "Urgent"],
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


def _decision(answers: list[dict]) -> Decision:
    """Return a decisions response with the given answers."""
    return Decision.model_validate(
        {
            "model": "decider",
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
async def evaluation_entry(
    hass: HomeAssistant, mock_openai_client: AsyncMock
) -> MockConfigEntry:
    """Set up a LiteLLM entry with an AI task evaluation subentry."""
    mock_openai_client.decisions.create = AsyncMock(return_value=_decision(ANSWERS))
    entry = MockConfigEntry(
        title="localhost:4000",
        domain=DOMAIN,
        data={CONF_URL: TEST_URL, CONF_API_KEY: "bla"},
        subentries_data=[
            ConfigSubentryData(
                data={CONF_MODEL: "decider"},
                subentry_id="EVALUATE",
                subentry_type="ai_task_evaluate",
                title="decider",
                unique_id=None,
            )
        ],
    )
    await setup_integration(hass, entry)
    return entry


async def _evaluate(
    hass: HomeAssistant, **kwargs: object
) -> ai_task.EvaluationTaskResult:
    """Run an evaluation task on the LiteLLM entity."""
    return await ai_task.async_evaluate(
        hass,
        task_name="Delivery",
        entity_id=ENTITY_ID,
        questions=QUESTIONS,
        **kwargs,
    )


@pytest.mark.usefixtures("evaluation_entry")
@pytest.mark.parametrize(
    ("state", "expected_input"),
    [
        pytest.param("Delivered", "Delivered", id="text"),
        pytest.param({"count": 2}, '{"count":2}', id="json"),
    ],
)
async def test_evaluate(
    hass: HomeAssistant,
    mock_openai_client: AsyncMock,
    state: object,
    expected_input: str,
) -> None:
    """Test all question types are sent to the decisions endpoint and answered."""
    result = await _evaluate(hass, state=state)

    assert result.answers == {
        "delivered": ai_task.NoulAnswer(noul=0.97),
        "location": ai_task.ChoiceAnswer(
            choice="door", probabilities={"door": 0.9, "other": 0.1}
        ),
        "attention": ai_task.ScoreAnswer(score=0.15, probabilities=[0.9, 0.05, 0.05]),
    }
    mock_openai_client.decisions.create.assert_awaited_once_with(
        model="decider",
        input=expected_input,
        questions=[
            {
                "type": "predicate",
                "name": "delivered",
                "instructions": "Was a package delivered?",
            },
            {
                "type": "choice",
                "name": "location",
                "instructions": "Where is the package?",
                "choices": [
                    {"value": "door", "description": "At the front door"},
                    {"value": "other", "description": "Somewhere else"},
                ],
            },
            {
                "type": "score",
                "name": "attention",
                "instructions": "How urgent is it?",
                "levels": [
                    {"label": "0", "description": "Not urgent"},
                    {"label": "1", "description": "Somewhat urgent"},
                    {"label": "2", "description": "Urgent"},
                ],
            },
        ],
    )


@pytest.mark.usefixtures("evaluation_entry")
@pytest.mark.parametrize(
    ("state", "expected_text"),
    [
        pytest.param(None, [], id="image-only"),
        pytest.param(
            "Look at the door",
            [{"type": "input_text", "text": "Look at the door"}],
            id="image-and-state",
        ),
    ],
)
async def test_evaluate_image(
    hass: HomeAssistant,
    mock_openai_client: AsyncMock,
    tmp_path: Path,
    state: str | None,
    expected_text: list[dict],
) -> None:
    """Test image attachments are sent as inline image parts."""
    image_path = tmp_path / "snapshot.jpg"
    image_path.write_bytes(b"image")
    with patch(
        "homeassistant.components.media_source.async_resolve_media",
        return_value=media_source.PlayMedia(
            url="/media/snapshot.jpg", mime_type="image/jpeg", path=image_path
        ),
    ):
        await _evaluate(
            hass,
            state=state,
            attachments=[
                {
                    "media_content_id": "media-source://media_source/local/snapshot.jpg",
                    "media_content_type": "image/jpeg",
                }
            ],
        )

    assert mock_openai_client.decisions.create.call_args.kwargs["input"] == [
        {
            "role": "user",
            "content": [
                *expected_text,
                {"type": "input_image", "image_url": "data:image/jpeg;base64,aW1hZ2U="},
            ],
        }
    ]


@pytest.mark.usefixtures("evaluation_entry")
async def test_evaluate_unsupported_attachment(
    hass: HomeAssistant, mock_openai_client: AsyncMock, tmp_path: Path
) -> None:
    """Test a non-image attachment is rejected before the proxy is called."""
    with (
        patch(
            "homeassistant.components.media_source.async_resolve_media",
            return_value=media_source.PlayMedia(
                url="/media/audio.wav",
                mime_type="audio/wav",
                path=tmp_path / "audio.wav",
            ),
        ),
        pytest.raises(HomeAssistantError, match="received audio/wav"),
    ):
        await _evaluate(
            hass,
            attachments=[
                {
                    "media_content_id": "media-source://media_source/local/audio.wav",
                    "media_content_type": "audio/wav",
                }
            ],
        )
    mock_openai_client.decisions.create.assert_not_called()


@pytest.mark.usefixtures("evaluation_entry")
@pytest.mark.parametrize(
    ("answers", "error"),
    [
        pytest.param(
            [*ANSWERS, {**ANSWERS[0], "name": "unknown"}],
            "unexpected question name: unknown",
            id="unknown-name",
        ),
        pytest.param(
            [*ANSWERS, ANSWERS[0]],
            "unexpected question name: delivered",
            id="duplicate-name",
        ),
        pytest.param(ANSWERS[:2], "no answer for attention", id="missing-answer"),
        pytest.param(
            [{"type": "refusal", "name": "delivered"}],
            "refused evaluation question delivered",
            id="refusal",
        ),
        pytest.param(
            [ANSWERS[0], {**ANSWERS[0], "name": "location"}, ANSWERS[2]],
            "predicate answer for choice question location",
            id="mismatched-type",
        ),
        pytest.param(
            [ANSWERS[0], {**ANSWERS[1], "choice": True}],
            "invalid choice for location",
            id="boolean-choice",
        ),
        pytest.param(
            [
                ANSWERS[0],
                {
                    **ANSWERS[1],
                    "choice": "garage",
                    "probabilities": [{"value": "garage", "probability": 1.0}],
                },
                ANSWERS[2],
            ],
            "invalid choice for location",
            id="unrequested-choice",
        ),
        pytest.param(
            [
                ANSWERS[0],
                {**ANSWERS[1], "probabilities": [ANSWERS[1]["probabilities"][0]] * 2},
            ],
            "invalid choice for location",
            id="duplicate-probability",
        ),
        pytest.param(
            [
                ANSWERS[0],
                ANSWERS[1],
                {**ANSWERS[2], "probabilities": [ANSWERS[2]["probabilities"][0]] * 3},
            ],
            "invalid score levels for attention",
            id="duplicate-level",
        ),
        pytest.param(
            [
                ANSWERS[0],
                ANSWERS[1],
                {**ANSWERS[2], "probabilities": ANSWERS[2]["probabilities"][1:]},
            ],
            "invalid score levels for attention",
            id="missing-level",
        ),
    ],
)
async def test_evaluate_invalid_response(
    hass: HomeAssistant,
    mock_openai_client: AsyncMock,
    answers: list[dict],
    error: str,
) -> None:
    """Test refusals and malformed backend answers raise an error."""
    mock_openai_client.decisions.create.return_value = _decision(answers)

    with pytest.raises(HomeAssistantError, match=error):
        await _evaluate(hass, state="Delivered")


@pytest.mark.usefixtures("evaluation_entry")
@pytest.mark.parametrize(
    ("side_effect", "available"),
    [
        pytest.param(
            APIConnectionError(request=httpx2.Request("POST", TEST_URL)),
            False,
            id="connection",
        ),
        pytest.param(OpenAIError("unknown model"), True, id="provider"),
    ],
)
async def test_evaluate_error(
    hass: HomeAssistant,
    mock_openai_client: AsyncMock,
    side_effect: Exception,
    available: bool,
) -> None:
    """Test only connection errors mark the evaluation entity unavailable."""
    mock_openai_client.decisions.create.side_effect = side_effect

    with pytest.raises(HomeAssistantError):
        await _evaluate(hass, state="Delivered")
    assert (hass.states.get(ENTITY_ID).state != STATE_UNAVAILABLE) is available


async def test_evaluate_auth_error_starts_reauth(
    hass: HomeAssistant,
    mock_openai_client: AsyncMock,
    evaluation_entry: MockConfigEntry,
) -> None:
    """Test a rejected API key starts reauthentication."""
    auth_error = AuthenticationError(
        message="invalid api key",
        response=httpx2.Response(401, request=httpx2.Request("POST", TEST_URL)),
        body=None,
    )
    mock_openai_client.decisions.create.side_effect = auth_error
    mock_openai_client.with_options.return_value.models.list.side_effect = auth_error

    with pytest.raises(HomeAssistantError, match="Authentication error"):
        await _evaluate(hass, state="Delivered")
    await hass.async_block_till_done()

    assert [
        flow["context"]["source"]
        for flow in evaluation_entry.async_get_active_flows(hass, {SOURCE_REAUTH})
    ] == [SOURCE_REAUTH]
