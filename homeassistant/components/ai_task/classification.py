"""Types and validation for image classification tasks."""

from dataclasses import dataclass
import io
from pathlib import Path
from typing import Any

from PIL import Image
import probatio

from homeassistant.components.conversation import Attachment
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import selector

from .evaluation import ChoiceAnswer


@dataclass(slots=True, frozen=True)
class Region:
    """Part of an image, as fractions of its size."""

    left: float = 0.0
    top: float = 0.0
    right: float = 1.0
    bottom: float = 1.0


@dataclass(slots=True)
class ImageLabel:
    """A label defined by example images."""

    examples: list[Attachment]
    description: str | None = None


@dataclass(slots=True)
class ClassifyImageTask:
    """An image to classify by the examples of each label."""

    name: str
    image: Attachment
    labels: dict[str, ImageLabel]
    region: Region | None = None
    instructions: str | None = None


class ImageUnusableError(HomeAssistantError):
    """The image shows nothing to classify, for example from an offline camera."""


def _require_image(value: dict[str, Any]) -> dict[str, Any]:
    """Require an image media type."""
    if not value["media_content_type"].startswith("image/"):
        raise probatio.Invalid("only images can be classified")
    return value


def _validate_region(value: dict[str, float]) -> dict[str, float]:
    """Require a region with a positive width and height."""
    if value["left"] >= value["right"] or value["top"] >= value["bottom"]:
        raise probatio.Invalid("left must be less than right, top less than bottom")
    return value


_FRACTION = probatio.All(probatio.Coerce(float), probatio.Range(min=0, max=1))
_NONEMPTY_STRING = probatio.All(str, probatio.Length(min=1))
IMAGE_SCHEMA = probatio.All(
    selector.MediaSelector({"accept": ["image/*"]}), _require_image
)


def _example(value: Any) -> dict[str, Any] | Attachment:
    """Accept a media source of an image, or from Python an image file."""
    if isinstance(value, Attachment):
        if not value.mime_type.startswith("image/"):
            raise probatio.Invalid("only images can be classified")
        return value
    media: dict[str, Any] = IMAGE_SCHEMA(value)
    return media


REGION_SCHEMA = probatio.Schema(
    probatio.All(
        {
            probatio.Optional("left", default=0.0): _FRACTION,
            probatio.Optional("top", default=0.0): _FRACTION,
            probatio.Optional("right", default=1.0): _FRACTION,
            probatio.Optional("bottom", default=1.0): _FRACTION,
        },
        _validate_region,
    )
)
LABELS_SCHEMA = probatio.Schema(
    probatio.All(
        {
            _NONEMPTY_STRING: {
                probatio.Required("examples"): probatio.All(
                    [_example], probatio.Length(min=1)
                ),
                probatio.Optional("description"): _NONEMPTY_STRING,
            }
        },
        probatio.Length(min=2),
    )
)


def validate_result(answer: ChoiceAnswer, labels: dict[str, Any]) -> bool:
    """Return whether an answer has a probability per label and a top choice."""
    probabilities = answer.probabilities
    return (
        probabilities.keys() == labels.keys()
        and all(0 <= value <= 1 for value in probabilities.values())
        and answer.choice in labels
        and probabilities[answer.choice] == max(probabilities.values())
    )


def crop_image(path: Path, region: Region | None) -> bytes:
    """Return the region of an image file as JPEG; blocking I/O."""
    with Image.open(path) as source:
        image = source.convert("RGB")
    if region is not None:
        width, height = image.size
        image = image.crop(
            (
                round(region.left * width),
                round(region.top * height),
                round(region.right * width),
                round(region.bottom * height),
            )
        )
    output = io.BytesIO()
    image.save(output, format="JPEG", quality=95)
    return output.getvalue()
