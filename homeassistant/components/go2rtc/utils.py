"""Utils for go2rtc component."""

from __future__ import annotations

import io
import logging
import os
import platform
import re
import stat
import subprocess
from tempfile import NamedTemporaryFile
from threading import Thread
from typing import Final
import zipfile

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

BINARY_VERSION = "1.9.4"

SYSTEM = {
    "Windows": {"AMD64": "go2rtc_win64.zip", "ARM64": "go2rtc_win_arm64.zip"},
    "Darwin": {"x86_64": "go2rtc_mac_amd64.zip", "arm64": "go2rtc_mac_arm64.zip"},
    "Linux": {
        "armv7l": "go2rtc_linux_arm",
        "armv8l": "go2rtc_linux_arm",  # https://github.com/AlexxIT/WebRTC/issues/18
        "aarch64": "go2rtc_linux_arm64",
        "x86_64": "go2rtc_linux_amd64",
        "i386": "go2rtc_linux_386",
        "i486": "go2rtc_linux_386",
        "i586": "go2rtc_linux_386",
        "i686": "go2rtc_linux_386",
    },
}

DEFAULT_URL = "http://localhost:1984/"

BINARY_NAME = re.compile(
    r"^(go2rtc-\d\.\d\.\d+|go2rtc_v0\.1-rc\.[5-9]|rtsp2webrtc_v[1-5])(\.exe)?$"
)


def _get_arch() -> str | None:
    system = SYSTEM.get(platform.system())
    if not system:
        return None
    return system.get(platform.machine())


def _unzip(content: bytes) -> bytes:
    with zipfile.ZipFile(io.BytesIO(content)) as zf:
        for filename in zf.namelist():
            with zf.open(filename) as f:
                return f.read()

    raise RuntimeError("Can't unzip binary")


async def validate_binary(hass: HomeAssistant) -> str | None:
    """Validate binary or download it."""
    filename = f"go2rtc-{BINARY_VERSION}"
    if platform.system() == "Windows":
        filename += ".exe"

    filename = hass.config.path(filename)
    if os.path.isfile(filename) and os.access(filename, os.X_OK):
        return filename

    # remove all old binaries
    for file in os.listdir(hass.config.config_dir):
        if BINARY_NAME.match(file):
            _LOGGER.debug("Remove old binary: %s", file)
            os.remove(hass.config.path(file))

    # download new binary
    url = (
        f"https://github.com/AlexxIT/go2rtc/releases/download/"
        f"v{BINARY_VERSION}/{_get_arch()}"
    )
    _LOGGER.debug("Download new binary: %s", url)
    r = await async_get_clientsession(hass).get(url)
    if not r.ok:
        return None

    raw = await r.read()

    # unzip binary for windows
    if url.endswith(".zip"):
        raw = _unzip(raw)

    # save binary to config folder
    # todo delete this file before merge
    with open(filename, "wb") as f:  # noqa: ASYNC230
        f.write(raw)

    # change binary access rights
    os.chmod(filename, os.stat(filename).st_mode | stat.S_IEXEC)

    return filename


class Server(Thread):
    """Server thread."""

    def __init__(self, binary: str) -> None:
        """Initialize the server."""
        super().__init__(name=DOMAIN, daemon=True)
        self._binary = binary
        self._stop_requested = False
        self.url: Final = DEFAULT_URL

    def run(self) -> None:
        """Run the server."""
        self._stop_requested = False
        with (
            NamedTemporaryFile(prefix="go2rtc", suffix=".yaml") as file,
            subprocess.Popen(
                [self._binary, "-c", "webrtc.ice_servers=[]", "-c", file.name],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            ) as process,
        ):
            while not self._stop_requested and process.poll() is None:
                assert process.stdout
                line = process.stdout.readline()
                if line == b"":
                    break
                _LOGGER.debug(line[:-1].decode())

            process.terminate()

    def stop(self) -> None:
        """Stop the server."""
        self._stop_requested = True
        if self.is_alive():
            self.join()
