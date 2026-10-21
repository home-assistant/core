"""Test image classification tasks and their result contract."""

from collections.abc import Generator
from pathlib import Path
from unittest.mock import AsyncMock, patch

from PIL import Image
import probatio
import pytest
from pytest_homeassistant.common import MockUser

from homeassistant.components import ai_task
from homeassistant.components.ai_task.const import DATA_PREFERENCES
from homeassistant.components.conversation import Attachment
from homeassistant.components.media_source import MediaImage
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import (
    HomeAssistantError,
    ServiceValidationError,
    Unauthorized,
)

from .conftest import TEST_ENTITY_ID, MockAITaskEntity

IMAGE = {
    "media_content_id": "media-source://camera/camera.garage",
    "media_content_type": "image/jpeg",
}


def _example(name: str) -> dict[str, str]:
    return {
        "media_content_id": f"media-source://media_source/local/garage/{name}.jpg",
        "media_content_type": "image/jpeg",
    }


LABELS = {
    "empty": {
        "description": "The bay is empty",
        "examples": [_example("empty_1"), _example("empty_2")],
    },
    "car": {"examples": [_example("car_1")]},
}
ANSWER = ai_task.ChoiceAnswer(choice="car", probabilities={"empty": 0.08, "car": 0.92})


@pytest.fixture(autouse=True)
def mock_classify(mock_ai_task_entity: MockAITaskEntity) -> Generator[AsyncMock]:
    """Enable image classification on the test entity."""
    mock_ai_task_entity._attr_supported_features = (
        ai_task.AITaskEntityFeature.CLASSIFY_IMAGE
    )
    with patch.object(
        mock_ai_task_entity, "_async_classify_image", return_value=ANSWER
    ) as mock:
        yield mock


@pytest.fixture(autouse=True)
def mock_media() -> Generator[AsyncMock]:
    """Return every media source as a JPEG holding its own ID."""

    async def get_image(hass: HomeAssistant, media_content_id: str) -> MediaImage:
        return MediaImage(mime_type="image/jpeg", content=media_content_id.encode())

    with patch(
        "homeassistant.components.media_source.async_get_media_image",
        side_effect=get_image,
    ) as mock:
        yield mock


async def _content(hass: HomeAssistant, attachment: Attachment) -> str:
    return (await hass.async_add_executor_job(attachment.path.read_bytes)).decode()


@pytest.mark.usefixtures("init_components")
@pytest.mark.freeze_time("2026-10-20 12:00:00")
async def test_classify_image(hass: HomeAssistant, mock_classify: AsyncMock) -> None:
    """Pass the image, every example per label and the region to the entity."""
    seen: dict[str, list[str]] = {}

    async def classify(task: ai_task.ClassifyImageTask) -> ai_task.ChoiceAnswer:
        seen["image"] = [await _content(hass, task.image)]
        for label_id, label in task.labels.items():
            seen[label_id] = [await _content(hass, e) for e in label.examples]
        return ANSWER

    mock_classify.side_effect = classify
    context = Context()
    response = await hass.services.async_call(
        "ai_task",
        "classify_image",
        {
            "task_name": "Left bay",
            "entity_id": TEST_ENTITY_ID,
            "image": IMAGE,
            "labels": LABELS,
            "region": {"left": 0.3, "right": 0.7},
            "instructions": "Is a car parked in the left bay?",
        },
        blocking=True,
        return_response=True,
        context=context,
    )

    assert response == {
        "type": "choice",
        "choice": "car",
        "probabilities": {"empty": 0.08, "car": 0.92},
    }
    task = mock_classify.call_args.args[0]
    assert task.name == "Left bay"
    assert task.region == ai_task.Region(left=0.3, top=0.0, right=0.7, bottom=1.0)
    assert task.instructions == "Is a car parked in the left bay?"
    assert task.labels["empty"].description == "The bay is empty"
    assert task.labels["car"].description is None
    assert seen == {
        "image": [IMAGE["media_content_id"]],
        "empty": [
            _example("empty_1")["media_content_id"],
            _example("empty_2")["media_content_id"],
        ],
        "car": [_example("car_1")["media_content_id"]],
    }
    entity_state = hass.states.get(TEST_ENTITY_ID)
    assert entity_state.context is context
    assert entity_state.state == "2026-10-20T12:00:00+00:00"


@pytest.mark.usefixtures("init_components")
async def test_preferred_entity(hass: HomeAssistant, mock_classify: AsyncMock) -> None:
    """Use the preferred entity without a region or instructions."""
    with pytest.raises(ServiceValidationError, match="no preferred entity"):
        await ai_task.async_classify_image(
            hass, task_name="Bay", image=IMAGE, labels=LABELS
        )

    hass.data[DATA_PREFERENCES].async_set_preferences(
        classify_image_entity_id=TEST_ENTITY_ID
    )
    assert (
        await ai_task.async_classify_image(
            hass, task_name="Bay", image=IMAGE, labels=LABELS
        )
        == ANSWER
    )
    task = mock_classify.call_args.args[0]
    assert task.region is None
    assert task.instructions is None


@pytest.mark.usefixtures("init_components")
async def test_feature_required(
    hass: HomeAssistant,
    mock_ai_task_entity: MockAITaskEntity,
    mock_classify: AsyncMock,
) -> None:
    """Reject entities without the feature, even with attachment support."""
    mock_ai_task_entity._attr_supported_features = (
        ai_task.AITaskEntityFeature.EVALUATE
        | ai_task.AITaskEntityFeature.SUPPORT_ATTACHMENTS
    )
    with pytest.raises(
        ServiceValidationError, match="does not support image classification"
    ):
        await ai_task.async_classify_image(
            hass,
            task_name="Bay",
            entity_id=TEST_ENTITY_ID,
            image=IMAGE,
            labels=LABELS,
        )
    mock_classify.assert_not_called()


@pytest.mark.usefixtures("init_components")
@pytest.mark.parametrize(
    "data",
    [
        pytest.param({"labels": {"car": LABELS["car"]}}, id="one_label"),
        pytest.param(
            {"labels": {"empty": {"examples": []}, "car": LABELS["car"]}},
            id="no_examples",
        ),
        pytest.param(
            {"labels": {"empty": {"description": "x"}, "car": LABELS["car"]}},
            id="missing_examples",
        ),
        pytest.param(
            {"labels": {"": LABELS["empty"], "car": LABELS["car"]}}, id="empty_id"
        ),
        pytest.param(
            {"labels": {"empty": {**LABELS["empty"], "description": ""}, "car": {}}},
            id="empty_description",
        ),
        pytest.param({"region": {"left": 0.5, "right": 0.5}}, id="no_width"),
        pytest.param({"region": {"top": 0.9, "bottom": 0.1}}, id="no_height"),
        pytest.param({"region": {"right": 1.5}}, id="outside"),
        pytest.param({"image": [IMAGE, IMAGE]}, id="two_images"),
        pytest.param({"instructions": ""}, id="empty_instructions"),
        pytest.param(
            {"image": {**IMAGE, "media_content_type": "video/mp4"}}, id="video"
        ),
        pytest.param(
            {
                "labels": {
                    **LABELS,
                    "car": {
                        "examples": [
                            {**_example("car_1"), "media_content_type": "video/mp4"}
                        ]
                    },
                }
            },
            id="video_example",
        ),
    ],
)
async def test_invalid_input(
    hass: HomeAssistant, mock_classify: AsyncMock, data: dict
) -> None:
    """Reject malformed labels, regions and images before running the task."""
    with pytest.raises(probatio.Invalid):
        await hass.services.async_call(
            "ai_task",
            "classify_image",
            {
                "task_name": "Bay",
                "entity_id": TEST_ENTITY_ID,
                "image": IMAGE,
                "labels": LABELS,
                **data,
            },
            blocking=True,
            return_response=True,
        )
    mock_classify.assert_not_called()


@pytest.mark.usefixtures("init_components")
async def test_example_permission(
    hass: HomeAssistant, hass_admin_user: MockUser, mock_classify: AsyncMock
) -> None:
    """Check read permission on the examples, not only on the image."""
    hass_admin_user.mock_policy(
        {
            "entities": {
                "entity_ids": {
                    TEST_ENTITY_ID: {"control": True},
                    "camera.garage": {"read": True},
                }
            }
        }
    )
    labels = {
        **LABELS,
        "car": {
            "examples": [
                {**IMAGE, "media_content_id": "media-source://camera/camera.x"}
            ]
        },
    }
    with (
        patch("homeassistant.components.ai_task.task._resolve_attachments") as resolve,
        pytest.raises(Unauthorized),
    ):
        await ai_task.async_classify_image(
            hass,
            task_name="Bay",
            entity_id=TEST_ENTITY_ID,
            image=IMAGE,
            labels=labels,
            context=Context(user_id=hass_admin_user.id),
        )
    resolve.assert_not_called()
    mock_classify.assert_not_called()


@pytest.mark.usefixtures("init_components")
@pytest.mark.parametrize(
    "answer",
    [
        pytest.param(
            ai_task.ChoiceAnswer(choice="car", probabilities={"car": 1.0}),
            id="missing_label",
        ),
        pytest.param(
            ai_task.ChoiceAnswer(
                choice="car", probabilities={"empty": 0.1, "car": 0.8, "van": 0.1}
            ),
            id="extra_label",
        ),
        pytest.param(
            ai_task.ChoiceAnswer(
                choice="car", probabilities={"empty": -0.1, "car": 1.1}
            ),
            id="out_of_range",
        ),
        pytest.param(
            ai_task.ChoiceAnswer(
                choice="empty", probabilities={"empty": 0.1, "car": 0.9}
            ),
            id="not_the_highest",
        ),
        pytest.param(
            ai_task.ChoiceAnswer(
                choice="van", probabilities={"empty": 0.5, "car": 0.5}
            ),
            id="unknown_choice",
        ),
        pytest.param(
            ai_task.ChoiceAnswer(
                choice="car", probabilities={"empty": 0.4, "car": 0.9}
            ),
            id="not_a_distribution",
        ),
    ],
)
async def test_invalid_result(
    hass: HomeAssistant, mock_classify: AsyncMock, answer: ai_task.ChoiceAnswer
) -> None:
    """Reject answers that break the result contract."""
    mock_classify.return_value = answer
    with pytest.raises(HomeAssistantError, match="invalid classification"):
        await ai_task.async_classify_image(
            hass,
            task_name="Bay",
            entity_id=TEST_ENTITY_ID,
            image=IMAGE,
            labels=LABELS,
        )


@pytest.mark.parametrize(
    ("region", "size", "color"),
    [
        pytest.param(None, (40, 20), (255, 0, 0), id="full"),
        pytest.param(
            ai_task.Region(left=0.5, top=0.0, right=1.0, bottom=1.0),
            (20, 20),
            (0, 0, 255),
            id="right_half",
        ),
    ],
)
def test_crop_image(
    tmp_path: Path,
    region: ai_task.Region | None,
    size: tuple[int, int],
    color: tuple[int, int, int],
) -> None:
    """Crop to the region and return a JPEG."""
    image = Image.new("RGB", (40, 20), (0, 0, 255))
    image.paste((255, 0, 0), (0, 0, 20, 20))
    path = tmp_path / "frame.png"
    image.save(path)

    cropped = ai_task.crop_image(path, region)

    (tmp_path / "crop.jpg").write_bytes(cropped)
    with Image.open(tmp_path / "crop.jpg") as result:
        assert result.format == "JPEG"
        assert result.size == size
        pixel = result.getpixel((0, size[1] // 2))
        assert all(abs(a - b) < 16 for a, b in zip(pixel, color, strict=True))


@pytest.mark.usefixtures("init_components")
async def test_attachment_examples(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
    mock_media: AsyncMock,
    mock_classify: AsyncMock,
    tmp_path: Path,
) -> None:
    """Pass image files from Python without resolving or permission checks."""
    hass_admin_user.mock_policy(
        {
            "entities": {
                "entity_ids": {
                    TEST_ENTITY_ID: {"control": True},
                    "camera.garage": {"read": True},
                }
            }
        }
    )
    stored = Attachment(
        media_content_id="image_classification/frame",
        mime_type="image/jpeg",
        path=tmp_path / "frame.jpg",
    )
    labels = {**LABELS, "car": {"examples": [stored]}}

    await ai_task.async_classify_image(
        hass,
        task_name="Bay",
        entity_id=TEST_ENTITY_ID,
        image=IMAGE,
        labels=labels,
        context=Context(user_id=hass_admin_user.id),
    )

    task = mock_classify.call_args.args[0]
    assert task.labels["car"].examples == [stored]
    assert len(task.labels["empty"].examples) == 2
    assert mock_media.call_count == 3


@pytest.mark.usefixtures("init_components")
async def test_attachment_examples_must_be_images(
    hass: HomeAssistant, mock_classify: AsyncMock, tmp_path: Path
) -> None:
    """Reject an attached file that is not an image."""
    clip = Attachment(
        media_content_id="clip", mime_type="video/mp4", path=tmp_path / "clip.mp4"
    )
    with pytest.raises(probatio.Invalid):
        await ai_task.async_classify_image(
            hass,
            task_name="Bay",
            entity_id=TEST_ENTITY_ID,
            image=IMAGE,
            labels={**LABELS, "car": {"examples": [clip]}},
        )
    mock_classify.assert_not_called()
