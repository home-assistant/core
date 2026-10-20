"""Frames taught to an Image classification entry."""

import asyncio
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from functools import partial
from pathlib import Path
import re
import shutil
from typing import Any
import uuid

from PIL import Image

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util
from homeassistant.util.hass_dict import HassKey

from .const import DOMAIN, LOGGER, STATES

STORAGE_VERSION = 1
FRAME_ID = re.compile(r"[0-9a-f]{32}")
FRAME_MIME_TYPE = "image/jpeg"
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


def frame_path(hass: HomeAssistant, entry_id: str, frame_id: str) -> Path:
    """Return the file of a taught frame."""
    return _folder(hass, entry_id) / f"{frame_id}.jpg"


def media_content_id(entry_id: str, frame_id: str) -> str:
    """Return the media source ID of a taught frame."""
    return f"media-source://{DOMAIN}/{entry_id}/{frame_id}.jpg"


def _folder(hass: HomeAssistant, entry_id: str) -> Path:
    return Path(hass.config.path(DOMAIN, entry_id))


def _store(hass: HomeAssistant, entry_id: str) -> Store[dict[str, Any]]:
    return Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry_id}")


def _lock(hass: HomeAssistant, entry_id: str) -> asyncio.Lock:
    return hass.data.setdefault(DATA_LOCKS, {}).setdefault(entry_id, asyncio.Lock())


class TaughtFrames:
    """Persists the taught frames of an entry as example images."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        """Initialize the taught frames."""
        self._hass = hass
        self._entry_id = entry_id
        self._store = _store(hass, entry_id)
        self._lock = _lock(hass, entry_id)
        self._closed = False
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

    @property
    def ready(self) -> bool:
        """Return whether every state has a frame to compare with."""
        return all(self.counts()[state] for state in STATES)

    def counts(self) -> Counter[str]:
        """Return the number of frames per state."""
        return Counter(item["label"] for item in self._items.values())

    def labels(self) -> dict[str, dict[str, Any]]:
        """Return the labels with their examples for an AI Task."""
        return {
            state: {
                "examples": [
                    {
                        "media_content_id": media_content_id(self._entry_id, frame_id),
                        "media_content_type": FRAME_MIME_TYPE,
                    }
                    for frame_id, item in self._items.items()
                    if item["label"] == state
                ]
            }
            for state in STATES
        }

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
            dropped = await self._hass.async_add_executor_job(self._check_files)
            for frame_id, reason in dropped.items():
                LOGGER.warning("Dropping taught frame %s: %s", frame_id, reason)
                del self._items[frame_id]
            if self._data and len(self._items) != len(self._data["frames"]):
                await self._async_save()

    def _check_files(self) -> dict[str, str]:
        """Return the frames whose file is unusable, with the reason."""
        dropped: dict[str, str] = {}
        for frame_id in self._items:
            path = self._path(frame_id)
            try:
                with Image.open(path) as image:
                    # A reduced decode still reads the whole file.
                    image.draft("RGB", (1, 1))
                    image.load()
            except FileNotFoundError:
                dropped[frame_id] = "file missing"
            except OSError as err:
                dropped[frame_id] = f"undecodable: {err}"
                path.unlink()
        # Files without an index item are left alone: after a damaged index
        # they are the only copy. Removing the entry deletes them.
        return dropped

    async def async_teach(self, frame: bytes, state: str) -> None:
        """Store a JPEG frame as an example of ``state``.

        Raises EntryClosed when the entry was unloaded.
        """
        # A closed dialog cancels the flow step, not a change half done.
        await asyncio.shield(
            self._hass.async_create_task(self._async_teach(frame, state))
        )

    async def _async_teach(self, frame: bytes, state: str) -> None:
        async with self._lock:
            self._check_open()
            frame_id = uuid.uuid4().hex
            await self._hass.async_add_executor_job(self._write, frame_id, frame)
            self._items[frame_id] = {
                "id": frame_id,
                "label": state,
                "created": dt_util.utcnow().isoformat(),
            }
            await self._async_save()

    def _write(self, frame_id: str, frame: bytes) -> None:
        path = self._path(frame_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(frame)

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
            await self._hass.async_add_executor_job(self._delete_files, frame_ids)
            for frame_id in frame_ids:
                del self._items[frame_id]
            await self._async_save()

    def _check_open(self) -> None:
        if self._closed:
            raise EntryClosed

    def _path(self, frame_id: str) -> Path:
        return frame_path(self._hass, self._entry_id, frame_id)

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
            and item["label"] in STATES
            and isinstance(datetime.fromisoformat(item["created"]), datetime)
        )
    except KeyError, TypeError, ValueError:
        return False
