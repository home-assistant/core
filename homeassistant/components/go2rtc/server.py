"""Go2rtc server."""

import asyncio
from collections import deque
from contextlib import suppress
import logging
from tempfile import NamedTemporaryFile

from aiohttp import ClientSession
from go2rtc_client import Go2RtcRestClient

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import HA_MANAGED_API_PORT, HA_MANAGED_URL
from .util import get_go2rtc_unix_socket_path

_LOGGER = logging.getLogger(__name__)
_TERMINATE_TIMEOUT = 5
_SETUP_TIMEOUT = 30
_SUCCESSFUL_BOOT_MESSAGE = "INF [api] listen addr="
_LOG_BUFFER_SIZE = 512
_RESPAWN_COOLDOWN = 1

# Default configuration for HA
# - Unix socket for secure local communication
# - Basic auth enabled, including local connections
# - HTTP API only enabled when UI is enabled
# - Enable rtsp for localhost only as ffmpeg needs it
# - Clear default ice servers
_GO2RTC_CONFIG_FORMAT = r"""# This file is managed by Home Assistant
# Do not edit it manually

app:
  modules: {app_modules}

api:
  listen: "{listen_config}"
  unix_listen: "{unix_socket}"
  allow_paths: {api_allow_paths}
  local_auth: true
  username: {username}
  password: {password}

# ffmpeg needs the exec module
# Restrict execution to only ffmpeg binary
exec:
  allow_paths:
    - ffmpeg

rtsp:
  listen: "127.0.0.1:18554"

webrtc:
  listen: ":18555/tcp"
  ice_servers: []
"""

_APP_MODULES = (
    "api",
    "exec",  # Execution module for ffmpeg
    "ffmpeg",
    "http",
    "mjpeg",
    "onvif",
    "rtmp",
    "rtsp",
    "srtp",
    "webrtc",
    "ws",
)

_API_ALLOW_PATHS = (
    "/",  # UI static page and version control
    "/api",  # Main API path
    "/api/frame.jpeg",  # Snapshot functionality
    "/api/schemes",  # Supported stream schemes
    "/api/streams",  # Stream management
    "/api/webrtc",  # Webrtc functionality
    "/api/ws",  # Websocket functionality (e.g. webrtc candidates)
)

# Additional modules when UI is enabled
_UI_APP_MODULES = (
    *_APP_MODULES,
    "debug",
)
# Additional api paths when UI is enabled
_UI_API_ALLOW_PATHS = (
    *_API_ALLOW_PATHS,
    "/api/config",  # UI config view
    "/api/log",  # UI log view
    "/api/streams.dot",  # UI network view
)

_LOG_LEVEL_MAP = {
    "TRC": logging.DEBUG,
    "DBG": logging.DEBUG,
    "INF": logging.DEBUG,
    "WRN": logging.WARNING,
    "ERR": logging.WARNING,
    "FTL": logging.ERROR,
    "PNC": logging.ERROR,
}


class Go2RTCServerStartError(HomeAssistantError):
    """Raised when server does not start."""

    _message = "Go2rtc server didn't start correctly"


class Go2RTCWatchdogError(HomeAssistantError):
    """Raised on watchdog error."""


def _format_list_for_yaml(items: tuple[str, ...]) -> str:
    """Format a list of strings for yaml config."""
    if not items:
        return "[]"
    formatted_items = ",".join(f'"{item}"' for item in items)
    return f"[{formatted_items}]"


def _create_temp_file(
    enable_ui: bool, username: str, password: str, working_dir: str
) -> str:
    """Create temporary config file."""
    app_modules: tuple[str, ...] = _APP_MODULES
    api_paths: tuple[str, ...] = _API_ALLOW_PATHS

    if enable_ui:
        app_modules = _UI_APP_MODULES
        api_paths = _UI_API_ALLOW_PATHS
        # Listen on all interfaces for allowing access from all ips
        listen_config = f":{HA_MANAGED_API_PORT}"
    else:
        # Disable HTTP listening when UI is not enabled
        # as HA does not use it.
        listen_config = ""

    # Set delete=False to prevent the file from being deleted when the file is closed
    # Linux is clearing tmp folder on reboot, so no need to delete it manually
    with NamedTemporaryFile(
        prefix="go2rtc_", suffix=".yaml", dir=working_dir, delete=False
    ) as file:
        file.write(
            _GO2RTC_CONFIG_FORMAT.format(
                listen_config=listen_config,
                unix_socket=get_go2rtc_unix_socket_path(working_dir),
                app_modules=_format_list_for_yaml(app_modules),
                api_allow_paths=_format_list_for_yaml(api_paths),
                username=username,
                password=password,
            ).encode()
        )
        return file.name


class Server:
    """Go2rtc server."""

    def __init__(
        self,
        hass: HomeAssistant,
        binary: str,
        session: ClientSession,
        *,
        enable_ui: bool = False,
        username: str,
        password: str,
        working_dir: str,
    ) -> None:
        """Initialize the server."""
        self._hass = hass
        self._binary = binary
        self._session = session
        self._enable_ui = enable_ui
        self._username = username
        self._password = password
        self._working_dir = working_dir
        self._log_buffer: deque[str] = deque(maxlen=_LOG_BUFFER_SIZE)
        self._process: asyncio.subprocess.Process | None = None
        self._startup_complete = asyncio.Event()
        self._watchdog_task: asyncio.Task | None = None
        self._watchdog_tasks: list[asyncio.Task] = []

    async def start(self) -> None:
        """Start the server."""
        await self._start()
        self._watchdog_task = asyncio.create_task(
            self._watchdog(), name="Go2rtc respawn"
        )

    async def _start(self) -> None:
        """Start the server."""
        _LOGGER.debug("Starting go2rtc server")
        config_file = await self._hass.async_add_executor_job(
            _create_temp_file,
            self._enable_ui,
            self._username,
            self._password,
            self._working_dir,
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
            self._log_server_output(logging.WARNING)
            await self._stop()
            raise Go2RTCServerStartError from err

        # Check the server version
        client = Go2RtcRestClient(self._session, HA_MANAGED_URL)
        await client.validate_server_version()

    async def _log_output(self, process: asyncio.subprocess.Process) -> None:
        """Log the output of the process."""
        assert process.stdout is not None

        async for line in process.stdout:
            msg = line[:-1].decode().strip()
            self._log_buffer.append(msg)
            loglevel = logging.WARNING
            if len(split_msg := msg.split(" ", 2)) == 3:
                loglevel = _LOG_LEVEL_MAP.get(split_msg[1], loglevel)
            _LOGGER.log(loglevel, msg)
            if not self._startup_complete.is_set() and _SUCCESSFUL_BOOT_MESSAGE in msg:
                self._startup_complete.set()

    def _log_server_output(self, loglevel: int) -> None:
        """Log captured process output, then clear the log buffer."""
        for line in list(self._log_buffer):  # Copy the deque to avoid mutation error
            _LOGGER.log(loglevel, line)
        self._log_buffer.clear()

    async def _watchdog(self) -> None:
        """Keep respawning go2rtc servers.

        A new go2rtc server is spawned if the process terminates or the API
        stops responding.
        """
        while True:
            try:
                monitor_process_task = asyncio.create_task(self._monitor_process())
                self._watchdog_tasks.append(monitor_process_task)
                monitor_process_task.add_done_callback(self._watchdog_tasks.remove)
                monitor_api_task = asyncio.create_task(self._monitor_api())
                self._watchdog_tasks.append(monitor_api_task)
                monitor_api_task.add_done_callback(self._watchdog_tasks.remove)
                try:
                    await asyncio.gather(monitor_process_task, monitor_api_task)
                except Go2RTCWatchdogError:
                    _LOGGER.debug("Caught Go2RTCWatchdogError")
                    for task in self._watchdog_tasks:
                        if task.done():
                            if not task.cancelled():
                                task.exception()
                            continue
                        task.cancel()
                    await asyncio.sleep(_RESPAWN_COOLDOWN)
                    try:
                        await self._stop()
                        _LOGGER.warning("Go2rtc unexpectedly stopped, server log:")
                        self._log_server_output(logging.WARNING)
                        _LOGGER.debug("Spawning new go2rtc server")
                        with suppress(Go2RTCServerStartError):
                            await self._start()
                    except Exception:
                        _LOGGER.exception(
                            "Unexpected error when restarting go2rtc server"
                        )
            except Exception:
                _LOGGER.exception("Unexpected error in go2rtc server watchdog")

    async def _monitor_process(self) -> None:
        """Raise if the go2rtc process terminates."""
        _LOGGER.debug("Monitoring go2rtc server process")
        if self._process:
            await self._process.wait()
        _LOGGER.debug("go2rtc server terminated")
        raise Go2RTCWatchdogError("Process ended")

    async def _monitor_api(self) -> None:
        """Raise if the go2rtc process terminates."""
        client = Go2RtcRestClient(self._session, HA_MANAGED_URL)

        _LOGGER.debug("Monitoring go2rtc API")
        try:
            while True:
                await client.validate_server_version()
                await asyncio.sleep(10)
        except Exception as err:
            _LOGGER.debug("go2rtc API did not reply", exc_info=True)
            raise Go2RTCWatchdogError("API error") from err

    async def _stop_watchdog(self) -> None:
        """Handle watchdog stop request."""
        tasks: list[asyncio.Task] = []
        if watchdog_task := self._watchdog_task:
            self._watchdog_task = None
            tasks.append(watchdog_task)
            watchdog_task.cancel()
        for task in self._watchdog_tasks:
            tasks.append(task)
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    async def stop(self) -> None:
        """Stop the server and abort the watchdog task."""
        _LOGGER.debug("Server stop requested")
        await self._stop_watchdog()
        await self._stop()

    async def _stop(self) -> None:
        """Stop the server."""
        if self._process:
            _LOGGER.debug("Stopping go2rtc server")
            process = self._process
            self._process = None
            with suppress(ProcessLookupError):
                process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=_TERMINATE_TIMEOUT)
            except TimeoutError:
                _LOGGER.warning("Go2rtc server didn't terminate gracefully. Killing it")
                with suppress(ProcessLookupError):
                    process.kill()
            else:
                _LOGGER.debug("Go2rtc server has been stopped")
