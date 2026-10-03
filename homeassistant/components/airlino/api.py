"""The API handling for Airlino (Lintech HBM11 HTTP API)."""

import asyncio
import logging
from typing import Any

import aiohttp

from .const import (
    API_TIMEOUT,
    DEFAULT_API_VERSION,
    DEFAULT_PORT,
    MULTIROOM_GROUP_NAME,
    PLAYER_STATE_PAUSED,
    PLAYER_STATE_PLAYING,
    PLAYER_STATE_STOPPED,
    RECEIVER_STATE_DISCONNECTED,
    RECEIVER_STATE_NOT_PLAYING,
    RECEIVER_STATE_OFF,
    RECEIVER_STATE_PLAYING,
    SONGCAST_MODE_UNICAST,
    VOLUME_MAX,
    VOLUME_MIN,
    VOLUME_STEP,
)

LOGGER = logging.getLogger(__name__)


class AirlinoApiError(Exception):
    """Raised when the device returns an error."""

    def __init__(self, message: str, *, status: int | None = None) -> None:
        """Initialize the error."""
        super().__init__(message)
        self.status = status


class AirlinoApiConnectionError(Exception):
    """Raised when the device cannot be reached."""


class AirlinoApi:
    """API access to AirLino devices.

    All requests are POST requests with a JSON body to
    http://<host>:<port>/api/<version>/<endpoint>.
    """

    def __init__(
        self,
        host: str,
        port: int = DEFAULT_PORT,
        timeout: float = API_TIMEOUT,
        session: aiohttp.ClientSession | None = None,
        api_version: str = DEFAULT_API_VERSION,
    ) -> None:
        """Initialize the API client."""
        self.host = host
        self.port = port
        self.timeout = timeout
        self.api_version = api_version
        self._session = session
        self._owns_session = session is None
        self._base_url = f"http://{host}:{port}/api/{api_version}"

    async def async_close(self) -> None:
        """Close the session if we own it."""
        if self._owns_session and self._session and not self._session.closed:
            await self._session.close()

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
            self._owns_session = True
        return self._session

    async def _request(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Send a POST request to the device and return the JSON response."""
        session = await self._get_session()
        url = f"{self._base_url}/{endpoint}"
        try:
            async with asyncio.timeout(self.timeout):
                async with session.post(
                    url,
                    json=payload,
                    # Old AirLino firmwares close the connection between
                    # requests, so keep-alive reuse fails.
                    headers={
                        "Content-Type": "application/json; charset=UTF-8",
                        "Connection": "close",
                    },
                ) as response:
                    response.raise_for_status()
                    try:
                        data: Any = await response.json(content_type=None)
                    except ValueError as err:
                        raise AirlinoApiError(f"{url} returned invalid JSON") from err
                    if not isinstance(data, dict):
                        raise AirlinoApiError(
                            f"{url} returned invalid response type: "
                            f"{type(data).__name__}"
                        )
        except TimeoutError as err:
            raise AirlinoApiConnectionError(
                f"Timeout while connecting to {url}"
            ) from err
        except aiohttp.ClientResponseError as err:
            raise AirlinoApiError(
                f"{url} returned HTTP {err.status}: {err.message}",
                status=err.status,
            ) from err
        except aiohttp.ClientError as err:
            raise AirlinoApiConnectionError(
                f"Error connecting to {url}: {err}"
            ) from err
        else:
            LOGGER.debug("POST %s %s -> %s", url, payload, data)
            return data

    async def _action(
        self, endpoint: str, action: str, **params: Any
    ) -> dict[str, Any]:
        """Send an action to an endpoint and validate the returncode."""
        payload: dict[str, Any] = {"action": action, **params}
        data = await self._request(endpoint, payload)
        if data.get("returncode") == "error":
            raise AirlinoApiError(f"{endpoint}/{action} returned error: {data}")
        return data

    # Device ----------------------------------------------------------------

    async def async_get_device_info(self) -> dict[str, Any]:
        """Get device information (model, devicename, firmware, hardware)."""
        data = await self._request("device.action", {"action": "info"})
        for key in ("model", "devicename", "firmware", "hardware"):
            value = data.get(key)
            if value is not None and not isinstance(value, str):
                raise AirlinoApiError(f"Device info field {key} must be a string")
        return data

    async def async_get_network_info(self) -> dict[str, Any]:
        """Get network information."""
        data = await self._request("network.action", {"action": "info"})
        for interface_name in ("eth", "wlan"):
            interface = data.get(interface_name)
            if interface is not None and not isinstance(interface, dict):
                raise AirlinoApiError(
                    f"Network info field {interface_name} must be an object"
                )
            if isinstance(interface, dict):
                mac = interface.get("mac")
                if mac is not None and not isinstance(mac, str):
                    raise AirlinoApiError(
                        f"Network info field {interface_name}.mac must be a string"
                    )
        return data

    # Player -----------------------------------------------------------------

    async def async_get_player_status(self) -> dict[str, Any]:
        """Get playback state and status information."""
        data = await self._request("player.action", {"action": "status"})
        state = data.get("state")
        if state is not None and (
            isinstance(state, bool)
            or not isinstance(state, int)
            or state
            not in (
                PLAYER_STATE_STOPPED,
                PLAYER_STATE_PLAYING,
                PLAYER_STATE_PAUSED,
            )
        ):
            raise AirlinoApiError("Player status contains an invalid state")
        status = data.get("status")
        if status is not None and not isinstance(status, dict):
            raise AirlinoApiError("Player status field status must be an object")
        if isinstance(status, dict):
            for key in ("station", "track"):
                value = status.get(key)
                if value is not None and not isinstance(value, dict):
                    raise AirlinoApiError(
                        f"Player status field status.{key} must be an object"
                    )
        return data

    async def async_play(self) -> None:
        """Start playback."""
        await self._action("player.action", "play")

    async def async_playpause(self) -> None:
        """Toggle between play and pause."""
        await self._action("player.action", "playpause")

    async def async_stop(self) -> None:
        """Stop playback."""
        await self._action("player.action", "stop")

    async def async_next(self) -> None:
        """Play next item from the playlist."""
        await self._action("player.action", "next")

    async def async_previous(self) -> None:
        """Play previous item from the playlist."""
        await self._action("player.action", "prev")

    # Radio ------------------------------------------------------------------

    async def async_play_station(
        self, url: str, name: str | None = None, image: str | None = None
    ) -> None:
        """Play a stream URL on the device (radio.action/play)."""
        station: dict[str, Any] = {"url": url}
        if name is not None:
            station["name"] = name
        if image is not None:
            station["image"] = image
        await self._action("radio.action", "play", station=station)

    # Sound ------------------------------------------------------------------

    async def async_get_master_volume(self) -> int:
        """Get the master volume level."""
        data = await self._request("sound.action", {"action": "getmastervol"})
        volume = data.get("volume")
        if isinstance(volume, bool) or not isinstance(volume, (int, str)):
            raise AirlinoApiError("Response is missing a valid volume")
        try:
            parsed_volume = int(volume)
        except ValueError as err:
            raise AirlinoApiError("Response contains an invalid volume") from err
        if not VOLUME_MIN <= parsed_volume <= VOLUME_MAX:
            raise AirlinoApiError("Response contains an out-of-range volume")
        return parsed_volume

    async def async_set_master_volume(self, volume: int) -> None:
        """Set the master volume level."""
        if isinstance(volume, bool) or not VOLUME_MIN <= volume <= VOLUME_MAX:
            raise AirlinoApiError("Volume must be within the supported range")
        await self._action("sound.action", "setmastervol", volume=volume)

    async def async_volume_up(self, step: int = VOLUME_STEP) -> None:
        """Increase master volume."""
        current = await self.async_get_master_volume()
        await self.async_set_master_volume(min(VOLUME_MAX, current + step))

    async def async_volume_down(self, step: int = VOLUME_STEP) -> None:
        """Decrease master volume."""
        current = await self.async_get_master_volume()
        await self.async_set_master_volume(max(VOLUME_MIN, current - step))

    # Songcast (multiroom) ---------------------------------------------------

    async def async_get_sender_status(self) -> dict[str, Any]:
        """Get the Songcast sender status (enabled, state, uuid, groupname, mode)."""
        data = await self._request("songcast/sender.action", {"action": "status"})
        enabled = data.get("enabled")
        if enabled is not None and not isinstance(enabled, (bool, int)):
            raise AirlinoApiError("Sender status field enabled must be boolean")
        uuid = data.get("uuid")
        if uuid is not None and not isinstance(uuid, str):
            raise AirlinoApiError("Sender status field uuid must be a string")
        return data

    async def async_enable_sender(
        self,
        groupname: str = MULTIROOM_GROUP_NAME,
        mode: int = SONGCAST_MODE_UNICAST,
    ) -> dict[str, Any]:
        """Enable the Songcast sender mode (unicast by default)."""
        try:
            return await self._action(
                "songcast/sender.action",
                "enable",
                groupname=groupname,
                mode=mode,
            )
        except AirlinoApiError as err:
            if "Already running" not in str(err):
                raise
            return {}

    async def async_disable_sender(self) -> None:
        """Disable the Songcast sender mode."""
        await self._action("songcast/sender.action", "disable")

    async def async_receiver_link(self, uuid: str) -> None:
        """Link this device as a Songcast receiver to a sender by its UUID."""
        await self._action("songcast/receiver.action", "link", uuid=uuid)

    async def async_receiver_unlink(self) -> None:
        """Unlink this Songcast receiver from its sender."""
        await self._action("songcast/receiver.action", "unlink")

    async def async_get_receiver_state(self) -> dict[str, Any]:
        """Get the current state of the Songcast receiver (state, sender UUID)."""
        data = await self._request("songcast/receiver.action", {"action": "state"})
        sender = data.get("sender")
        if sender is not None and not isinstance(sender, str):
            raise AirlinoApiError("Receiver state field sender must be a string")
        state = data.get("state")
        if state is not None and (
            isinstance(state, bool)
            or not isinstance(state, int)
            or state
            not in (
                RECEIVER_STATE_OFF,
                RECEIVER_STATE_NOT_PLAYING,
                RECEIVER_STATE_PLAYING,
                RECEIVER_STATE_DISCONNECTED,
            )
        ):
            raise AirlinoApiError("Receiver state field state is invalid")
        return data
