"""Test classifying images with the Local vision AI Task entity."""

from unittest.mock import patch

import pytest
from pytest_homeassistant.common import MockConfigEntry
from tarsius import StateDetector

from homeassistant.components import ai_task
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .conftest import scene

ENTITY_ID = "ai_task.local_vision"
IMAGE = "media-source://camera/camera.garage"


def _media(media_content_id: str) -> dict[str, str]:
    return {"media_content_id": media_content_id, "media_content_type": "image/jpeg"}


def _labels(empty: list[str], car: list[str]) -> dict[str, dict]:
    return {
        "empty": {"examples": [_media(i) for i in empty]},
        "car": {"examples": [_media(i) for i in car]},
    }


@pytest.fixture
def examples(media: dict[str, bytes]) -> dict[str, dict]:
    """Two examples per label."""
    for seed in range(2):
        media[f"empty_{seed}"] = scene(car=False, seed=seed)
        media[f"car_{seed}"] = scene(car=True, seed=seed)
    return _labels(["empty_0", "empty_1"], ["car_0", "car_1"])


async def _classify(
    hass: HomeAssistant, labels: dict[str, dict], **kwargs: object
) -> ai_task.ClassifyImageResult:
    return await ai_task.async_classify_image(
        hass,
        task_name="Bay",
        entity_id=ENTITY_ID,
        image=_media(IMAGE),
        labels=labels,
        **kwargs,
    )


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize("car", [True, False])
@pytest.mark.parametrize(
    "region",
    [
        pytest.param(None, id="full"),
        pytest.param({"left": 0.2, "top": 0.3, "right": 0.8, "bottom": 0.9}, id="bay"),
    ],
)
async def test_classify(
    hass: HomeAssistant,
    media: dict[str, bytes],
    examples: dict[str, dict],
    car: bool,
    region: dict[str, float] | None,
) -> None:
    """Pick the label whose examples look like the image."""
    media[IMAGE] = scene(car=car, seed=50)

    answer = await _classify(hass, examples, region=region)

    expected = "car" if car else "empty"
    assert answer.label == expected
    assert answer.probabilities[expected] > 0.5
    assert sum(answer.probabilities.values()) == pytest.approx(1.0)


@pytest.mark.usefixtures("init_integration")
async def test_examples_extracted_once(
    hass: HomeAssistant, media: dict[str, bytes], examples: dict[str, dict]
) -> None:
    """Reuse detectors and extract each example of a region only once."""
    media[IMAGE] = scene(car=True, seed=50)
    with patch.object(
        StateDetector, "prepare", autospec=True, side_effect=StateDetector.prepare
    ) as prepare:
        await _classify(hass, examples)
        assert prepare.call_count == 4

        await _classify(hass, examples)
        assert prepare.call_count == 4

        # empty_1 moves to car, car_1 is dropped: a new detector, no extraction.
        answer = await _classify(hass, _labels(["empty_0"], ["car_0", "empty_1"]))
        assert prepare.call_count == 4
    assert set(answer.probabilities) == {"empty", "car"}


@pytest.mark.usefixtures("init_integration")
async def test_detectors_are_bounded(
    hass: HomeAssistant, media: dict[str, bytes], examples: dict[str, dict]
) -> None:
    """Drop the detector used longest ago."""
    media[IMAGE] = scene(car=True, seed=50)
    with (
        patch("homeassistant.components.local_vision.ai_task.MAX_DETECTORS", 1),
        patch.object(
            StateDetector, "prepare", autospec=True, side_effect=StateDetector.prepare
        ) as prepare,
    ):
        await _classify(hass, examples)
        await _classify(hass, examples, region={"left": 0.5})
        await _classify(hass, examples)
    # The extracted examples outlive the dropped detector.
    assert prepare.call_count == 8


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("image", "example", "message"),
    [
        pytest.param(
            scene(car=True, seed=0, grey=True), None, "shows nothing", id="blank_image"
        ),
        pytest.param(b"garbage", None, "could not be read", id="garbage_image"),
        pytest.param(
            None,
            scene(car=True, seed=0, grey=True),
            "example of car shows nothing",
            id="blank_example",
        ),
        pytest.param(None, b"garbage", "could not be read", id="garbage_example"),
    ],
)
async def test_unusable_images(
    hass: HomeAssistant,
    media: dict[str, bytes],
    examples: dict[str, dict],
    image: bytes | None,
    example: bytes | None,
    message: str,
) -> None:
    """Explain why an image or an example cannot be used."""
    media[IMAGE] = image or scene(car=True, seed=50)
    if example is not None:
        media["car_1"] = example
    with pytest.raises(HomeAssistantError, match=message):
        await _classify(hass, examples)


async def test_entity(hass: HomeAssistant, init_integration: MockConfigEntry) -> None:
    """Expose one entity that only classifies images."""
    state = hass.states.get(ENTITY_ID)
    assert state.attributes["supported_features"] == (
        ai_task.AITaskEntityFeature.CLASSIFY_IMAGE
    )


@pytest.mark.usefixtures("init_integration")
async def test_blank_image_is_unusable(
    hass: HomeAssistant, media: dict[str, bytes], examples: dict[str, dict]
) -> None:
    """Tell callers that a blank frame has nothing to classify."""
    media[IMAGE] = scene(car=True, seed=0, grey=True)
    with pytest.raises(ai_task.ImageUnusableError):
        await _classify(hass, examples)


@pytest.mark.usefixtures("init_integration")
async def test_example_sets_do_not_mix(
    hass: HomeAssistant, media: dict[str, bytes], examples: dict[str, dict]
) -> None:
    """Callers with other examples for the same region get their own answer."""
    media[IMAGE] = scene(car=True, seed=50)
    swapped = _labels(["car_0", "car_1"], ["empty_0", "empty_1"])

    assert (await _classify(hass, examples)).label == "car"
    assert (await _classify(hass, swapped)).label == "empty"
    assert (await _classify(hass, examples)).label == "car"


@pytest.mark.usefixtures("init_integration")
async def test_examples_are_bounded(
    hass: HomeAssistant, media: dict[str, bytes], examples: dict[str, dict]
) -> None:
    """Drop the extracted examples used longest ago."""
    media[IMAGE] = scene(car=True, seed=50)
    with (
        patch("homeassistant.components.local_vision.ai_task.MAX_DETECTORS", 1),
        patch("homeassistant.components.local_vision.ai_task.MAX_EXAMPLES", 1),
        patch.object(
            StateDetector, "prepare", autospec=True, side_effect=StateDetector.prepare
        ) as prepare,
    ):
        await _classify(hass, examples)
        await _classify(hass, examples, region={"left": 0.5})
        await _classify(hass, examples)
    assert prepare.call_count == 12


@pytest.mark.usefixtures("init_integration")
async def test_example_in_two_labels(
    hass: HomeAssistant, media: dict[str, bytes], examples: dict[str, dict]
) -> None:
    """Reject the same image as an example of two labels."""
    media[IMAGE] = scene(car=True, seed=50)
    with pytest.raises(HomeAssistantError, match="example of two labels"):
        await _classify(hass, _labels(["empty_0", "car_0"], ["car_0"]))
