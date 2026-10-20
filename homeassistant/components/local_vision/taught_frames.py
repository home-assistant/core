"""Frames taught to a Local vision entry."""

import asyncio
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from functools import partial
from pathlib import Path
import re
import shutil
from typing import Any
import uuid

from tarsius import LoadReport, Result, StateDetector

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util
from homeassistant.util.hass_dict import HassKey

from .const import DOMAIN, LOGGER

STORAGE_VERSION = 1
FRAME_ID = re.compile(r"[0-9a-f]{32}")
# One lock per entry, shared by the instances of a reload and by removal.
DATA_LOCKS: HassKey[dict[str, asyncio.Lock]] = HassKey(f"{DOMAIN}_locks")


@dataclass(frozen=True, slots=True)
class TaughtFrame:
    """A frame the user confirmed with a label, the state it shows."""

    id: str
    label: str
    created: datetime


class EntryClosed(Exception):
    """The entry was unloaded while a change waited for it."""


def _folder(hass: HomeAssistant, entry_id: str) -> Path:
    return Path(hass.config.path(DOMAIN, entry_id))


def _store(hass: HomeAssistant, entry_id: str) -> Store[dict[str, Any]]:
    return Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry_id}")


def _lock(hass: HomeAssistant, entry_id: str) -> asyncio.Lock:
    return hass.data.setdefault(DATA_LOCKS, {}).setdefault(entry_id, asyncio.Lock())


class TaughtFrames:
    """Persists taught frames and keeps the detector in sync with them."""

    def __init__(
        self, hass: HomeAssistant, entry_id: str, detector: StateDetector
    ) -> None:
        """Initialize the taught frames."""
        self._hass = hass
        self._folder = _folder(hass, entry_id)
        self._store = _store(hass, entry_id)
        self._lock = _lock(hass, entry_id)
        self._closed = False
        self.detector = detector
        # Raw stored data, so fields written by newer versions survive a save.
        self._data: dict[str, Any] = {}
        self._items: dict[str, dict[str, Any]] = {}

    @property
    def frames(self) -> list[TaughtFrame]:
        """Return the taught frames, oldest first."""
        return [
            TaughtFrame(
                item["id"], item["label"], datetime.fromisoformat(item["created"])
            )
            for item in self._items.values()
        ]

    def close(self) -> None:
        """Refuse further changes, the entry is unloaded."""
        self._closed = True

    async def async_load(self) -> None:
        """Load the stored frames and drop those that can no longer be used."""
        async with self._lock:
            data = await self._store.async_load()
            if isinstance(data, dict) and isinstance(data.get("frames"), list):
                self._data = data
            else:
                self._data = {}
            self._items = {}
            for item in self._data.get("frames", []):
                if _valid(item):
                    self._items[item["id"]] = item
                else:
                    LOGGER.warning("Dropping invalid taught frame entry %r", item)
            report, missing = await self._hass.async_add_executor_job(self._load)
            for frame_id, reason in report.skipped.items():
                LOGGER.warning("Dropping taught frame %s: %s", frame_id, reason)
            for frame_id in missing:
                LOGGER.warning("Dropping taught frame %s: file missing", frame_id)
            dropped = [*report.skipped, *report.evicted, *missing]
            for frame_id in dropped:
                del self._items[frame_id]
            if self._data and len(self._items) != len(self._data["frames"]):
                await self._async_save()

    def _load(self) -> tuple[LoadReport, list[str]]:
        stored: list[tuple[str, bytes, str]] = []
        missing: list[str] = []
        for frame_id, item in self._items.items():
            try:
                stored.append(
                    (frame_id, self._path(frame_id).read_bytes(), item["label"])
                )
            except FileNotFoundError:
                missing.append(frame_id)
        report = self.detector.load(stored)
        # Files without an index item are left alone: after a damaged index
        # they are the only copy. Removing the entry deletes them.
        self._delete_files([*report.skipped, *report.evicted])
        return report, missing

    async def async_teach(self, frame: bytes, state: str) -> None:
        """Store a frame as a reference for ``state``.

        Raises tarsius ImageError, BlankFrameError, BlankRegionError or BackendError before
        anything is stored, EntryClosed when the entry was unloaded.
        """
        # A closed dialog cancels the flow step, not a change half done.
        await asyncio.shield(
            self._hass.async_create_task(self._async_teach(frame, state))
        )

    async def _async_teach(self, frame: bytes, state: str) -> None:
        async with self._lock:
            self._check_open()
            frame_id = uuid.uuid4().hex
            evicted = await self._hass.async_add_executor_job(
                self._teach, frame_id, frame, state
            )
            self._items[frame_id] = {
                "id": frame_id,
                "label": state,
                "created": dt_util.utcnow().isoformat(),
            }
            for evicted_id in evicted:
                self._items.pop(evicted_id, None)
            await self._async_save()

    def _teach(self, frame_id: str, frame: bytes, state: str) -> list[str]:
        prepared = self.detector.prepare(frame)
        self._folder.mkdir(parents=True, exist_ok=True)
        self._path(frame_id).write_bytes(prepared.original)
        evicted = self.detector.add(frame_id, prepared, state=state)
        self._delete_files(evicted)
        return evicted

    async def async_remove(self, frame_ids: Iterable[str]) -> None:
        """Remove taught frames; raise EntryClosed when the entry was unloaded."""
        await asyncio.shield(
            self._hass.async_create_task(self._async_remove(list(frame_ids)))
        )

    async def _async_remove(self, frame_ids: list[str]) -> None:
        async with self._lock:
            self._check_open()
            frame_ids = [
                frame_id
                for frame_id in dict.fromkeys(frame_ids)
                if frame_id in self._items
            ]
            await self._hass.async_add_executor_job(self._remove, frame_ids)
            for frame_id in frame_ids:
                del self._items[frame_id]
            await self._async_save()

    def _remove(self, frame_ids: list[str]) -> None:
        self.detector.remove(frame_ids)
        self._delete_files(frame_ids)

    def classify(self, frame: bytes) -> Result:
        """Classify a camera frame; blocking."""
        return self.detector.classify(frame)

    def _check_open(self) -> None:
        if self._closed:
            raise EntryClosed

    def _path(self, frame_id: str) -> Path:
        return self._folder / f"{frame_id}.jpg"

    def _delete_files(self, frame_ids: Iterable[str]) -> None:
        for frame_id in frame_ids:
            self._path(frame_id).unlink(missing_ok=True)

    async def _async_save(self) -> None:
        await self._store.async_save(
            {**self._data, "frames": list(self._items.values())}
        )


async def async_remove_taught_frames(hass: HomeAssistant, entry_id: str) -> None:
    """Delete all stored data of a removed entry."""

    # The shared parent folder stays, another entry may be creating its own.
    async with _lock(hass, entry_id):
        await _store(hass, entry_id).async_remove()
        await hass.async_add_executor_job(
            partial(shutil.rmtree, _folder(hass, entry_id), ignore_errors=True)
        )
    hass.data[DATA_LOCKS].pop(entry_id, None)


def _valid(item: Any) -> bool:
    """Return whether a stored index item can be used."""
    try:
        return (
            FRAME_ID.fullmatch(item["id"]) is not None
            and isinstance(item["label"], str)
            and isinstance(datetime.fromisoformat(item["created"]), datetime)
        )
    except KeyError, TypeError, ValueError:
        return False
