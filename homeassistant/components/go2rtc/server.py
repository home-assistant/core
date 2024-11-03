"""Go2rtc server."""

import asyncio
import logging
from tempfile import NamedTemporaryFile

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

_LOGGER = logging.getLogger(__name__)
_TERMINATE_TIMEOUT = 5
_SETUP_TIMEOUT = 30
_SUCCESSFUL_BOOT_MESSAGE = "INF [api] listen addr="
_LOCALHOST_IP = "127.0.0.1"
# Default configuration for HA
# - Api is listening only on localhost
# - Disable rtsp listener
# - Clear default ice servers
_GO2RTC_CONFIG_FORMAT = r"""
api:
  listen: "{api_ip}:1984"

rtsp:
  # ffmpeg needs rtsp for opus audio transcoding
  listen: "127.0.0.1:8554"

webrtc:
  ice_servers: []
"""


def _create_temp_file(api_ip: str) -> str:
    """Create temporary config file."""
    # Set delete=False to prevent the file from being deleted when the file is closed
    # Linux is clearing tmp folder on reboot, so no need to delete it manually
    with NamedTemporaryFile(prefix="go2rtc_", suffix=".yaml", delete=False) as file:
        file.write(_GO2RTC_CONFIG_FORMAT.format(api_ip=api_ip).encode())
        return file.name


class Server:
    """Go2rtc server."""

    def __init__(
        self, hass: HomeAssistant, binary: str, *, enable_ui: bool = False
    ) -> None:
        """Initialize the server."""
        self._hass = hass
        self._binary = binary
        self._process: asyncio.subprocess.Process | None = None
        self._startup_complete = asyncio.Event()
        self._api_ip = _LOCALHOST_IP
        if enable_ui:
            # Listen on all interfaces for allowing access from all ips
            self._api_ip = ""

    async def start(self) -> None:
        """Start the server."""
        _LOGGER.debug("Starting go2rtc server")
        config_file = await self._hass.async_add_executor_job(
            _create_temp_file, self._api_ip
        )

        self._startup_complete.clear()

        self._process = await asyncio.create_subprocess_exec(
            self._binary,
            "-c",
            config_file,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            close_fds=False,  # required for posix_spawn on CPython < 3.13
        )

        self._hass.async_create_background_task(
            self._log_output(self._process), "Go2rtc log output"
        )

        try:
            async with asyncio.timeout(_SETUP_TIMEOUT):
                await self._startup_complete.wait()
        except TimeoutError as err:
            msg = "Go2rtc server didn't start correctly"
            _LOGGER.exception(msg)
            await self.stop()
            raise HomeAssistantError("Go2rtc server didn't start correctly") from err

    async def _log_output(self, process: asyncio.subprocess.Process) -> None:
        """Log the output of the process."""
        assert process.stdout is not None

        async for line in process.stdout:
            msg = line[:-1].decode().strip()
            _LOGGER.debug(msg)
            if not self._startup_complete.is_set() and _SUCCESSFUL_BOOT_MESSAGE in msg:
                self._startup_complete.set()

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
