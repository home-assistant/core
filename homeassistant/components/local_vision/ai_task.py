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

# Detectors kept for the regions and labels asked for most recently.
MAX_DETECTORS = 16


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
            tuple[tuple[float, ...], tuple[str, ...]], StateDetector
        ] = OrderedDict()
        self._lock = threading.Lock()

    @override
    async def _async_classify_image(
        self, task: ai_task.ClassifyImageTask
    ) -> ai_task.ChoiceAnswer:
        """Classify the image in the executor."""
        return await self.hass.async_add_executor_job(self._classify, task)

    def _classify(self, task: ai_task.ClassifyImageTask) -> ai_task.ChoiceAnswer:
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
        probabilities = dict(result.probabilities)
        return ai_task.ChoiceAnswer(
            choice=max(probabilities, key=probabilities.__getitem__),
            probabilities=probabilities,
        )

    def _taught_detector(
        self, roi: Roi, task: ai_task.ClassifyImageTask
    ) -> StateDetector:
        """Return a detector for the region with exactly the task's examples."""
        key = (roi.as_tuple(), tuple(task.labels))
        if (detector := self._detectors.get(key)) is None:
            detector = StateDetector(roi, tuple(task.labels), backend=self._backend)
            self._detectors[key] = detector
            if len(self._detectors) > MAX_DETECTORS:
                self._detectors.popitem(last=False)
        self._detectors.move_to_end(key)
        # Examples are keyed by content, so a detector only extracts new ones.
        wanted: dict[str, tuple[str, bytes]] = {}
        for label_id, label in task.labels.items():
            for example in label.examples:
                data = example.path.read_bytes()
                wanted[hashlib.sha256(data).hexdigest()] = (label_id, data)
        known = detector.references()
        detector.remove([ref for ref in known if ref not in wanted])
        for ref, (label_id, data) in wanted.items():
            if known.get(ref) == label_id:
                continue
            try:
                detector.add(ref, detector.prepare(data), state=label_id)
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
        return detector
