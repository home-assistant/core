"""Utils for go2rtc component."""

from __future__ import annotations

import logging
import subprocess
from tempfile import NamedTemporaryFile
from threading import Thread

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class Server(Thread):
    """Server thread."""

    def __init__(self, binary: str) -> None:
        """Initialize the server."""
        super().__init__(name=DOMAIN, daemon=True)
        self._binary = binary
        self._stop_requested = False

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
