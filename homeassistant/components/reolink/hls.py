"""HLS playback of Reolink recordings downloaded using the Baichuan protocol."""

import asyncio
from contextlib import aclosing, suppress
from datetime import datetime
import logging
from pathlib import Path
import secrets
import shutil
import tempfile
from typing import Any

from reolink_aio.api import Host
from reolink_aio.exceptions import ReolinkError

from homeassistant.components.ffmpeg import get_ffmpeg_manager
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers.event import async_call_later

_LOGGER = logging.getLogger(__name__)

# Seconds without a request after which the downloaded files are removed
IDLE_TIMEOUT = 600
# Seconds to wait for a file to be downloaded, the HLS player gives up after 30 seconds
FILE_TIMEOUT = 25
# Folder in the temp dir holding the folders of the playbacks
HLS_DIR = "reolink_hls"


def _hls_root() -> Path:
    """Return the folder holding the folders of the playbacks."""
    return Path(tempfile.gettempdir()) / HLS_DIR


def _make_playback_dir() -> Path:
    """Create a new folder for the files of a playback."""
    root = _hls_root()
    root.mkdir(exist_ok=True)
    return Path(tempfile.mkdtemp(dir=root))


async def async_remove_leftover_hls_files(hass: HomeAssistant) -> None:
    """Remove the files of playbacks which were not closed, e.g. due to a crash.

    Only call this before any playback is started.
    """
    await hass.async_add_executor_job(shutil.rmtree, _hls_root(), True)


class ReolinkHlsPlayback:
    """Download a recording as HLS files and serve them while downloading.

    The recording is downloaded once from start to end, faster than real time.
    The playlist lists all segments from the start, so the player can seek in
    the full timeline: a request for a segment which is not downloaded yet
    waits until the download reaches it.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        api: Host,
        channel: int,
        stream: str,
        start: datetime,
        end: datetime,
    ) -> None:
        """Initialize the HLS playback."""
        self.token = secrets.token_hex()
        self._hass = hass
        self._config_entry = config_entry
        self._name = f"{api.camera_name(channel)} {start}"
        self._hls_files = api.baichuan.stream_hls(
            channel, start, end, stream, get_ffmpeg_manager(hass).binary
        )
        self._dir: Path | None = None
        self._downloaded: set[str] = set()  # names of the downloaded files
        self._finished = False
        self._progress = asyncio.Condition()
        self._task: asyncio.Task[None] | None = None
        self._cancel_idle: CALLBACK_TYPE | None = None

    async def async_start(self) -> None:
        """Start downloading the recording to a temporary directory."""
        self._dir = await self._hass.async_add_executor_job(_make_playback_dir)
        # background task of the config entry: cancelled when the config entry unloads
        self._task = self._config_entry.async_create_background_task(
            self._hass,
            self._async_download(self._dir),
            f"Reolink HLS download {self._name}",
        )
        self._async_restart_idle_timer()

    async def _async_download(self, directory: Path) -> None:
        """Write the HLS files to the temporary directory as they are received."""
        try:
            # aclosing: stop ffmpeg and the download directly when cancelled
            async with aclosing(self._hls_files) as hls_files:
                async for name, data in hls_files:
                    await self._hass.async_add_executor_job(
                        (directory / name).write_bytes, data
                    )
                    self._downloaded.add(name)
                    await self._async_notify_progress()
        except (ReolinkError, OSError) as err:
            _LOGGER.warning(
                "Reolink playback error while downloading %s: %s", self._name, err
            )
        finally:
            self._finished = True
            await self._async_notify_progress()

    async def _async_notify_progress(self) -> None:
        """Wake up the requests waiting for a file."""
        async with self._progress:
            self._progress.notify_all()

    async def async_get_file(self, name: str) -> Path | None:
        """Return the path of a HLS file, wait until it is downloaded.

        Returns None if the file will not be downloaded (anymore).
        """
        if self._dir is None:
            return None  # closed
        self._async_restart_idle_timer()
        try:
            async with asyncio.timeout(FILE_TIMEOUT), self._progress:
                await self._progress.wait_for(
                    lambda: name in self._downloaded or self._finished
                )
        except TimeoutError:
            return None
        if name not in self._downloaded or self._dir is None:
            return None
        return self._dir / name

    def _async_restart_idle_timer(self) -> None:
        """Remove the downloaded files when there are no requests for a while."""
        if self._cancel_idle is not None:
            self._cancel_idle()
        self._cancel_idle = async_call_later(self._hass, IDLE_TIMEOUT, self.async_close)

    async def async_close(self, *_: Any) -> None:
        """Stop the download and remove the downloaded files."""
        if self._cancel_idle is not None:
            self._cancel_idle()
            self._cancel_idle = None
        if self._task is not None:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        self._downloaded.clear()
        if self._dir is not None:
            directory = self._dir
            self._dir = None
            await self._hass.async_add_executor_job(shutil.rmtree, directory, True)
