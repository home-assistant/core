"""AI Task entity that classifies images locally with tarsius."""

from collections import OrderedDict
import hashlib
import threading
from typing import override

from tarsius import (
    FULL_FRAME,
    BlankFrameError,
    BlankRegionError,
    ImageError,
    Prepared,
    Roi,
    StateDetector,
)

from homeassistant.components import ai_task
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import LocalVisionConfigEntry
from .const import DOMAIN

PARALLEL_UPDATES = 0

# Detectors kept for the example sets asked for most recently.
MAX_DETECTORS = 16
# Extracted examples kept across detectors, enough for a few helpers.
MAX_EXAMPLES = 256


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LocalVisionConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the AI Task entity."""
    async_add_entities([LocalVisionTaskEntity(entry)])


class LocalVisionTaskEntity(ai_task.AITaskEntity):
    """Classify images by comparing them with the examples of each label."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_features = ai_task.AITaskEntityFeature.CLASSIFY_IMAGE

    def __init__(self, entry: LocalVisionConfigEntry) -> None:
        """Initialize the entity."""
        self._backend = entry.runtime_data
        self._attr_unique_id = entry.entry_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            entry_type=DeviceEntryType.SERVICE,
        )
        self._detectors: OrderedDict[
            tuple[tuple[float, ...], tuple[str, ...], frozenset[tuple[str, str]]],
            StateDetector,
        ] = OrderedDict()
        self._examples: OrderedDict[tuple[tuple[float, ...], str], Prepared] = (
            OrderedDict()
        )
        self._lock = threading.Lock()

    @override
    async def _async_classify_image(
        self, task: ai_task.ClassifyImageTask
    ) -> ai_task.ClassifyImageResult:
        """Classify the image in the executor."""
        return await self.hass.async_add_executor_job(self._classify, task)

    def _classify(self, task: ai_task.ClassifyImageTask) -> ai_task.ClassifyImageResult:
        region = task.region
        roi = (
            FULL_FRAME
            if region is None
            else Roi(region.left, region.top, region.right, region.bottom)
        )
        with self._lock:
            detector = self._taught_detector(roi, task)
        try:
            result = detector.classify(task.image.path.read_bytes())
        except BlankFrameError as err:
            raise ai_task.ImageUnusableError(
                translation_domain=DOMAIN, translation_key="blank_frame"
            ) from err
        except ImageError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="unreadable_image"
            ) from err
        # Unsure when the best state does not beat the others by the margin.
        return ai_task.ClassifyImageResult(
            label=result.state, probabilities=dict(result.probabilities)
        )

    def _taught_detector(
        self, roi: Roi, task: ai_task.ClassifyImageTask
    ) -> StateDetector:
        """Return a detector taught with exactly the task's examples.

        A detector never changes after it is taught, so callers with other
        examples for the same region never see each other's references.
        """
        examples: list[tuple[str, str, bytes]] = []
        for label_id, label in task.labels.items():
            for example in label.examples:
                data = example.path.read_bytes()
                examples.append((hashlib.sha256(data).hexdigest(), label_id, data))
        labels_of: dict[str, set[str]] = {}
        for ref, label_id, _ in examples:
            labels_of.setdefault(ref, set()).add(label_id)
        if any(len(labels) > 1 for labels in labels_of.values()):
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="example_in_two_labels"
            )
        key = (
            roi.as_tuple(),
            tuple(task.labels),
            frozenset((ref, label_id) for ref, label_id, _ in examples),
        )
        if (detector := self._detectors.get(key)) is not None:
            self._detectors.move_to_end(key)
            return detector
        detector = StateDetector(roi, tuple(task.labels), backend=self._backend)
        for ref, label_id, data in examples:
            detector.add(
                ref, self._prepared(detector, roi, ref, label_id, data), state=label_id
            )
        self._detectors[key] = detector
        if len(self._detectors) > MAX_DETECTORS:
            self._detectors.popitem(last=False)
        return detector

    def _prepared(
        self, detector: StateDetector, roi: Roi, ref: str, label_id: str, data: bytes
    ) -> Prepared:
        """Return the extracted example, shared by detectors of the same region."""
        key = (roi.as_tuple(), ref)
        if (prepared := self._examples.get(key)) is not None:
            self._examples.move_to_end(key)
            return prepared
        try:
            prepared = detector.prepare(data)
        except BlankRegionError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="blank_example",
                translation_placeholders={"label": label_id},
            ) from err
        except ImageError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="unreadable_image"
            ) from err
        self._examples[key] = prepared
        if len(self._examples) > MAX_EXAMPLES:
            self._examples.popitem(last=False)
        return prepared
