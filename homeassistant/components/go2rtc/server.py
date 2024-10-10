"""Go2rtc server."""

from __future__ import annotations

import logging
import subprocess
from tempfile import NamedTemporaryFile
from threading import Event, Thread

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class Server(Thread):
    """Server thread."""

    def __init__(self, binary: str) -> None:
        """Initialize the server."""
        super().__init__(name=DOMAIN, daemon=True)
        self._binary = binary
        self._process: subprocess.Popen | None = None
        self._stop_event = Event()

    def run(self) -> None:
        """Run the server."""
        _LOGGER.debug("Starting go2rtc server")
        self._stop_event.clear()
        with (
            NamedTemporaryFile(prefix="go2rtc", suffix=".yaml") as file,
            subprocess.Popen(
                [self._binary, "-c", "webrtc.ice_servers=[]", "-c", file.name],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            ) as process,
        ):
            self._process = process
            while process.poll() is None and not self._stop_event.is_set():
                assert process.stdout
                for line in process.stdout:
                    _LOGGER.debug(line[:-1].decode())
        self._process = None
        _LOGGER.debug("Go2rtc server has been stopped")

    def _terminate_process(self):
        """Terminate the subprocess, ensuring cleanup."""
        self._stop_event.set()

        if not self._process:
            return

        _LOGGER.debug("Terminating go2rtc server")
        self._process.terminate()
        try:
            self._process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _LOGGER.warning("Go2rtc server didn't terminate gracefully. Killing it.")
            self._process.kill()

    def stop(self) -> None:
        """Stop the server."""
        self._terminate_process()
        if self.is_alive():
            self.join()
