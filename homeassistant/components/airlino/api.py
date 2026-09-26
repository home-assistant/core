"""The API handling for Airlino (Lintech HBM11 HTTP API)."""

import asyncio
import logging
from typing import Any

import aiohttp

from .const import API_TIMEOUT, DEFAULT_API_VERSION, DEFAULT_PORT, MULTIROOM_GROUP_NAME

LOGGER = logging.getLogger(__name__)


class AirlinoApiError(Exception):
    """Raised when the device returns an error."""


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
                        data: dict[str, Any] = await response.json(content_type=None)
                    except ValueError as err:
                        body = await response.text()
                        raise AirlinoApiError(
                            f"{url} returned invalid JSON ({body[:200]!r}): {err}"
                        ) from err
        except TimeoutError as err:
            raise AirlinoApiConnectionError(
                f"Timeout while connecting to {url}"
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
        return await self._request("device.action", {"action": "info"})

    async def async_get_network_info(self) -> dict[str, Any]:
        """Get network information."""
        return await self._request("network.action", {"action": "info"})

    # Player -----------------------------------------------------------------

    async def async_get_player_status(self) -> dict[str, Any]:
        """Get playback state and status information."""
        return await self._request("player.action", {"action": "status"})

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
        """Get the master volume level (0-255)."""
        data = await self._request("sound.action", {"action": "getmastervol"})
        volume = data.get("volume")
        if volume is None:
            raise AirlinoApiError(f"Missing volume in response: {data}")
        return int(volume)

    async def async_set_master_volume(self, volume: int) -> None:
        """Set the master volume level (0-255)."""
        await self._action("sound.action", "setmastervol", volume=volume)

    async def async_volume_up(self, step: int = 10) -> None:
        """Increase master volume."""
        current = await self.async_get_master_volume()
        await self.async_set_master_volume(min(255, current + step))

    async def async_volume_down(self, step: int = 10) -> None:
        """Decrease master volume."""
        current = await self.async_get_master_volume()
        await self.async_set_master_volume(max(0, current - step))

    # Songcast (multiroom) ---------------------------------------------------

    async def async_get_sender_status(self) -> dict[str, Any]:
        """Get the Songcast sender status (enabled, state, uuid, groupname, mode)."""
        return await self._request("songcast/sender.action", {"action": "status"})

    async def async_enable_sender(
        self, groupname: str = MULTIROOM_GROUP_NAME, mode: int = 0
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
        return await self._request("songcast/receiver.action", {"action": "state"})
