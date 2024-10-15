"""Go2rtc server."""

import asyncio
import logging
from tempfile import NamedTemporaryFile

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)
_TERMINATE_TIMEOUT = 5


def _create_temp_file() -> str:
    """Create temporary config file."""
    # Set delete=False to prevent the file from being deleted when the file is closed
    # Linux is clearing tmp folder on reboot, so no need to delete it manually
    with NamedTemporaryFile(prefix="go2rtc", suffix=".yaml", delete=False) as file:
        return file.name


async def _log_output(process: asyncio.subprocess.Process) -> None:
    """Log the output of the process."""
    assert process.stdout is not None

    async for line in process.stdout:
        _LOGGER.debug(line[:-1].decode().strip())


class Server:
    """Go2rtc server."""

    def __init__(self, hass: HomeAssistant, binary: str) -> None:
        """Initialize the server."""
        self._hass = hass
        self._binary = binary
        self._process: asyncio.subprocess.Process | None = None

    async def start(self) -> None:
        """Start the server."""
        _LOGGER.debug("Starting go2rtc server")
        config_file = await self._hass.async_add_executor_job(_create_temp_file)

        self._process = await asyncio.create_subprocess_exec(
            self._binary,
            "-c",
            "webrtc.ice_servers=[]",
            "-c",
            config_file,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )

        self._hass.async_create_background_task(
            _log_output(self._process), "Go2rtc log output"
        )

    async def stop(self) -> None:
        """Stop the server."""
        if self._process:
            _LOGGER.debug("Stopping go2rtc server")
            process = self._process
            self._process = None
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=_TERMINATE_TIMEOUT)
            except TimeoutError:
                _LOGGER.warning("Go2rtc server didn't terminate gracefully. Killing it")
                process.kill()
            else:
                _LOGGER.debug("Go2rtc server has been stopped")
