"""Runtime state for Assist pipelines."""

import asyncio
from collections import defaultdict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from homeassistant.helpers.collection import CHANGE_UPDATED
from homeassistant.util import dt as dt_util, ulid as ulid_util
from homeassistant.util.hass_dict import HassKey
from homeassistant.util.limited_size_dict import LimitedSizeDict

from .audio_output import PipelineAudioOutputManager
from .const import DOMAIN
from .models import PipelineEvent

if TYPE_CHECKING:
    from .pipeline import PipelineStorageCollection
    from .run import PipelineRun


class PipelineRuns:
    """Class managing pipeline runs."""

    def __init__(self, pipeline_store: PipelineStorageCollection) -> None:
        """Initialize."""
        self._pipeline_runs: dict[str, dict[str, PipelineRun]] = defaultdict(dict)
        self._pipeline_store = pipeline_store
        pipeline_store.async_add_listener(self._change_listener)

    def add_run(self, pipeline_run: PipelineRun) -> None:
        """Add pipeline run."""
        pipeline_id = pipeline_run.pipeline.id
        self._pipeline_runs[pipeline_id][pipeline_run.id] = pipeline_run

    def remove_run(self, pipeline_run: PipelineRun) -> None:
        """Remove pipeline run."""
        pipeline_id = pipeline_run.pipeline.id
        self._pipeline_runs[pipeline_id].pop(pipeline_run.id)

    async def _change_listener(
        self, change_type: str, item_id: str, change: dict
    ) -> None:
        """Handle pipeline store changes."""
        if change_type != CHANGE_UPDATED:
            return
        if pipeline_runs := self._pipeline_runs.get(item_id):
            for pipeline_run in list(pipeline_runs.values()):
                pipeline_run.invalidate()


@dataclass(slots=True)
class DeviceAudioQueue:
    """Audio capture queue for a satellite device."""

    queue: asyncio.Queue[bytes | None]
    """Queue of audio chunks (None = stop signal)"""

    id: str = field(default_factory=ulid_util.ulid_now)
    """Unique id to ensure the correct audio queue is cleaned up in websocket API."""

    overflow: bool = False
    """Flag to be set if audio samples were dropped because the queue was full."""


@dataclass(slots=True)
class AssistDevice:
    """Assist device."""

    domain: str
    unique_id_prefix: str


class PipelineData:
    """Store and debug data stored in hass.data."""

    def __init__(self, pipeline_store: PipelineStorageCollection) -> None:
        """Initialize."""
        self.audio_output_manager = PipelineAudioOutputManager(pipeline_store.hass)
        self.pipeline_store = pipeline_store
        self.pipeline_debug: dict[str, LimitedSizeDict[str, PipelineRunDebug]] = {}
        self.pipeline_devices: dict[str, AssistDevice] = {}
        self.pipeline_runs = PipelineRuns(pipeline_store)
        self.device_audio_queues: dict[str, DeviceAudioQueue] = {}


@dataclass(slots=True)
class PipelineRunDebug:
    """Debug data for a pipeline run."""

    events: list[PipelineEvent] = field(default_factory=list, init=False)
    timestamp: str = field(
        default_factory=lambda: dt_util.utcnow().isoformat(),
        init=False,
    )


KEY_ASSIST_PIPELINE: HassKey[PipelineData] = HassKey(DOMAIN)
