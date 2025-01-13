"""Local backup support for Core and Container installations."""

from __future__ import annotations

import asyncio
from pathlib import Path
from queue import SimpleQueue
import tarfile
from typing import cast

import aiohttp
from securetar import SecureTarFile

from homeassistant.backup_restore import password_to_key
from homeassistant.core import HomeAssistant
from homeassistant.util.json import JsonObjectType, json_loads_object

from .const import BUF_SIZE, LOGGER
from .models import AddonInfo, AgentBackup, Folder


def make_backup_dir(path: Path) -> None:
    """Create a backup directory if it does not exist."""
    path.mkdir(exist_ok=True)


def read_backup(backup_path: Path) -> AgentBackup:
    """Read a backup from disk."""

    with tarfile.open(backup_path, "r:", bufsize=BUF_SIZE) as backup_file:
        if not (data_file := backup_file.extractfile("./backup.json")):
            raise KeyError("backup.json not found in tar file")
        data = json_loads_object(data_file.read())
        addons = [
            AddonInfo(
                name=cast(str, addon["name"]),
                slug=cast(str, addon["slug"]),
                version=cast(str, addon["version"]),
            )
            for addon in cast(list[JsonObjectType], data.get("addons", []))
        ]

        folders = [
            Folder(folder)
            for folder in cast(list[str], data.get("folders", []))
            if folder != "homeassistant"
        ]

        homeassistant_included = False
        homeassistant_version: str | None = None
        database_included = False
        if (
            homeassistant := cast(JsonObjectType, data.get("homeassistant"))
        ) and "version" in homeassistant:
            homeassistant_included = True
            homeassistant_version = cast(str, homeassistant["version"])
            database_included = not cast(
                bool, homeassistant.get("exclude_database", False)
            )

        return AgentBackup(
            addons=addons,
            backup_id=cast(str, data["slug"]),
            database_included=database_included,
            date=cast(str, data["date"]),
            extra_metadata=cast(dict[str, bool | str], data.get("extra", {})),
            folders=folders,
            homeassistant_included=homeassistant_included,
            homeassistant_version=homeassistant_version,
            name=cast(str, data["name"]),
            protected=cast(bool, data.get("protected", False)),
            size=backup_path.stat().st_size,
        )


def validate_password(path: Path, password: str | None) -> bool:
    """Validate the password."""
    with tarfile.open(path, "r:", bufsize=BUF_SIZE) as backup_file:
        compressed = False
        ha_tar_name = "homeassistant.tar"
        try:
            ha_tar = backup_file.extractfile(ha_tar_name)
        except KeyError:
            compressed = True
            ha_tar_name = "homeassistant.tar.gz"
            try:
                ha_tar = backup_file.extractfile(ha_tar_name)
            except KeyError:
                LOGGER.error("No homeassistant.tar or homeassistant.tar.gz found")
                return False
        try:
            with SecureTarFile(
                path,  # Not used
                gzip=compressed,
                key=password_to_key(password) if password is not None else None,
                mode="r",
                fileobj=ha_tar,
            ):
                # If we can read the tar file, the password is correct
                return True
        except tarfile.ReadError:
            LOGGER.debug("Invalid password")
            return False
        except Exception:  # noqa: BLE001
            LOGGER.exception("Unexpected error validating password")
    return False


async def receive_file(
    hass: HomeAssistant, contents: aiohttp.BodyPartReader, path: Path
) -> None:
    """Receive a file from a stream and write it to a file."""
    queue: SimpleQueue[tuple[bytes, asyncio.Future[None] | None] | None] = SimpleQueue()

    def _sync_queue_consumer() -> None:
        with path.open("wb") as file_handle:
            while True:
                if (_chunk_future := queue.get()) is None:
                    break
                _chunk, _future = _chunk_future
                if _future is not None:
                    hass.loop.call_soon_threadsafe(_future.set_result, None)
                file_handle.write(_chunk)

    fut: asyncio.Future[None] | None = None
    try:
        fut = hass.async_add_executor_job(_sync_queue_consumer)
        megabytes_sending = 0
        while chunk := await contents.read_chunk(BUF_SIZE):
            megabytes_sending += 1
            if megabytes_sending % 5 != 0:
                queue.put_nowait((chunk, None))
                continue

            chunk_future = hass.loop.create_future()
            queue.put_nowait((chunk, chunk_future))
            await asyncio.wait(
                (fut, chunk_future),
                return_when=asyncio.FIRST_COMPLETED,
            )
            if fut.done():
                # The executor job failed
                break

        queue.put_nowait(None)  # terminate queue consumer
    finally:
        if fut is not None:
            await fut
