"""Test AI Task evaluation for OpenRouter."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import openai
from openai.types.chat import ChatCompletion, ChatCompletionMessage
from openai.types.chat.chat_completion import Choice
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components import ai_task, media_source
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.json import json_dumps

from . import setup_integration

from tests.common import MockConfigEntry

ENTITY_ID = "ai_task.gpt_4"

QUESTIONS: dict[str, ai_task.EvaluationQuestion] = {
    "delivered": {"type": "noul", "instructions": "Has the package arrived?"},
    "location": {
        "type": "choice",
        "instructions": "Where was the package left?",
        "criteria": {"door": "At the front door", "garage": "In the garage"},
    },
    "urgency": {
        "type": "score",
        "instructions": "How urgent is it to collect the package?",
        "criteria": ["Not urgent", "Somewhat urgent", "Very urgent"],
    },
}


def _completion(content: str | None) -> ChatCompletion:
    """Build a chat completion with the given content."""
    return ChatCompletion(
        id="chatcmpl-1234567890ABCDEFGHIJKLMNOPQRS",
        choices=[
            Choice(
                finish_reason="stop",
                index=0,
                message=ChatCompletionMessage(content=content, role="assistant"),
            )
        ],
        created=1700000000,
        model="openai/gpt-4",
        object="chat.completion",
    )


async def test_evaluate(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openai_client: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test evaluating questions."""
    await setup_integration(hass, mock_config_entry)

    mock_openai_client.chat.completions.create = AsyncMock(
        return_value=_completion(
            json_dumps(
                {
                    "delivered": 0.9,
                    "location": {"door": 0.375, "garage": 0.125},
                    "urgency": {"0": 0.25, "1": 0.5, "2": 0.25},
                }
            )
        )
    )

    result = await ai_task.async_evaluate(
        hass,
        task_name="Check delivery",
        entity_id=ENTITY_ID,
        questions=QUESTIONS,
        state={"message": "Your package was left at the front door."},
    )

    assert result.as_dict() == {
        "answers": {
            "delivered": {"type": "noul", "noul": 0.9},
            "location": {
                "type": "choice",
                "choice": "door",
                "probabilities": {"door": 0.75, "garage": 0.25},
            },
            "urgency": {
                "type": "score",
                "score": 1.0,
                "probabilities": [0.25, 0.5, 0.25],
            },
        }
    }
    assert mock_openai_client.chat.completions.create.call_args.kwargs == snapshot


async def test_evaluate_with_attachments(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openai_client: AsyncMock,
) -> None:
    """Test evaluating questions with an image attachment and no state."""
    await setup_integration(hass, mock_config_entry)

    mock_openai_client.chat.completions.create = AsyncMock(
        return_value=_completion(json_dumps({"delivered": 1}))
    )

    with (
        patch(
            "homeassistant.components.media_source.async_resolve_media",
            return_value=media_source.PlayMedia(
                url="http://example.com/doorbell_snapshot.jpg",
                mime_type="image/jpeg",
                path=Path("doorbell_snapshot.jpg"),
            ),
        ),
        patch("pathlib.Path.exists", return_value=True),
        patch.object(hass.config, "is_allowed_path", return_value=True),
        patch("pathlib.Path.read_bytes", return_value=b"fake_image_data"),
    ):
        result = await ai_task.async_evaluate(
            hass,
            task_name="Check delivery",
            entity_id=ENTITY_ID,
            questions={"delivered": QUESTIONS["delivered"]},
            attachments=[
                {
                    "media_content_id": "media-source://media/doorbell_snapshot.jpg",
                    "media_content_type": "image/jpeg",
                }
            ],
        )

    assert result.answers == {"delivered": ai_task.NoulAnswer(noul=1.0)}
    content = mock_openai_client.chat.completions.create.call_args.kwargs["messages"][
        1
    ]["content"]
    assert content == [
        {
            "type": "text",
            "text": "Question delivered: Has the package arrived?\n"
            "Answer with the probability that the answer is yes.",
        },
        {
            "type": "image_url",
            "image_url": {"url": "data:image/jpeg;base64,ZmFrZV9pbWFnZV9kYXRh"},
        },
    ]


@pytest.mark.parametrize(
    ("content", "message"),
    [
        pytest.param(None, "OpenRouter returned an empty evaluation", id="empty"),
        pytest.param(
            "not json", "Error with OpenRouter structured response", id="invalid_json"
        ),
        pytest.param(
            json_dumps({"delivered": 0.5}),
            "OpenRouter returned unexpected questions",
            id="missing_question",
        ),
        pytest.param(
            json_dumps(
                {
                    "delivered": 1.5,
                    "location": {"door": 0.5, "garage": 0.5},
                    "urgency": {"0": 1, "1": 0, "2": 0},
                }
            ),
            "OpenRouter returned an invalid probability for question delivered",
            id="noul_out_of_range",
        ),
        pytest.param(
            json_dumps(
                {
                    "delivered": True,
                    "location": {"door": 0.5, "garage": 0.5},
                    "urgency": {"0": 1, "1": 0, "2": 0},
                }
            ),
            "OpenRouter returned an invalid probability for question delivered",
            id="noul_bool",
        ),
        pytest.param(
            json_dumps(
                {
                    "delivered": 0.5,
                    "location": {"door": 0.5},
                    "urgency": {"0": 1, "1": 0, "2": 0},
                }
            ),
            "OpenRouter returned invalid probabilities for question location",
            id="choice_missing_option",
        ),
        pytest.param(
            json_dumps(
                {
                    "delivered": 0.5,
                    "location": {"door": "high", "garage": 0.5},
                    "urgency": {"0": 1, "1": 0, "2": 0},
                }
            ),
            "OpenRouter returned invalid probabilities for question location",
            id="choice_not_number",
        ),
        pytest.param(
            json_dumps(
                {
                    "delivered": 0.5,
                    "location": {"door": 0.5, "garage": 0.5},
                    "urgency": {"0": 0, "1": 0, "2": 0},
                }
            ),
            "OpenRouter returned invalid probabilities for question urgency",
            id="score_all_zero",
        ),
    ],
)
async def test_evaluate_invalid_response(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openai_client: AsyncMock,
    content: str | None,
    message: str,
) -> None:
    """Test invalid evaluation responses raise an error."""
    await setup_integration(hass, mock_config_entry)

    mock_openai_client.chat.completions.create = AsyncMock(
        return_value=_completion(content)
    )

    with pytest.raises(HomeAssistantError, match=message):
        await ai_task.async_evaluate(
            hass,
            task_name="Check delivery",
            entity_id=ENTITY_ID,
            questions=QUESTIONS,
            state="Your package was left at the front door.",
        )


async def test_evaluate_api_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openai_client: AsyncMock,
) -> None:
    """Test API errors raise an error."""
    await setup_integration(hass, mock_config_entry)

    mock_openai_client.chat.completions.create = AsyncMock(
        side_effect=openai.OpenAIError("boom")
    )

    with pytest.raises(
        HomeAssistantError, match="Error evaluating OpenRouter task: boom"
    ):
        await ai_task.async_evaluate(
            hass,
            task_name="Check delivery",
            entity_id=ENTITY_ID,
            questions=QUESTIONS,
            state="Your package was left at the front door.",
        )
