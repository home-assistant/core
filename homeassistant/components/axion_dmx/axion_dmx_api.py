"""API client for Axion Lighting DMX Controller."""

import asyncio
import socket

from .const import _LOGGER


class AxionDmxApi:
    """Class to interact with the Axion Lighting DMX Controller."""

    def __init__(self, host: str, password: str) -> None:
        """Initialize the API client."""
        self._host = host
        self._port = 4005
        self._password = password

    async def _send_command(self, command: str) -> str:
        """Send a command to the Axion Lighting DMX controller and return the response."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:  # No event loop is running
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return await loop.run_in_executor(None, self._send_tcp_command, command)

    def _send_tcp_command(self, command: str) -> str:
        """Send a command to the Axion Lighting DMX controller over TCP and return the response."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.connect((self._host, self._port))
            sock.sendall(f">login,{self._password}\r\n".encode())
            response = sock.recv(1024).decode()
            if "ok" in response:
                _LOGGER.debug(f"Sending command: {command}")
                sock.sendall(command.encode())
                response = sock.recv(1024).decode()
            return response

    async def authenticate(self) -> bool:
        """Test if we can authenticate with the controller."""
        response = await self._send_command(">getversion\r\n")
        return "ok" in response

    async def set_level(self, channel: int, level: int) -> bool:
        """Set the level of a specific channel."""
        _LOGGER.debug(f"Setting the {channel} channel level to {level}")
        response = await self._send_command(f">setlevel,{channel},{level}\r\n")
        return "ok" in response

    async def get_level(self, channel: int) -> int:
        """Get the level of a specific channel."""
        response = await self._send_command(f">getlevel,{channel}\r\n")
        if "ok" in response:
            _LOGGER.debug(
                f"Level of DMX {channel} - {int(float(response.split(",")[1]))}"
            )
            return int(float(response.split(",")[1]))
        return 0

    async def set_color(self, channel: int, rgb: tuple[int, int, int]) -> bool:
        """Set the color of a specific channel."""
        r, g, b = rgb
        _LOGGER.debug(f"Setting R channel - channel {channel}, level - {r}")
        response = await self._send_command(f">setlevel,{channel},{r}\r\n")
        _LOGGER.debug(f"Setting G channel - channel {channel + 1}, level - {g}")
        response1 = await self._send_command(f">setlevel,{channel + 1},{g}\r\n")
        _LOGGER.debug(f"Setting B channel - channel {channel + 2}, level - {b}")
        response2 = await self._send_command(f">setlevel,{channel + 2},{b}\r\n")

        return "ok" in response and "ok" in response1 and "ok" in response2

    async def set_rgbw(self, channel: int, rgbw: tuple[int, int, int, int]) -> bool:
        """Set the RGBW color of a specific channel."""
        r, g, b, w = rgbw
        _LOGGER.debug(f"Setting R channel - channel {channel}, level - {r}")
        response = await self._send_command(f">setlevel,{channel},{r}\r\n")
        _LOGGER.debug(f"Setting G channel - channel {channel + 1}, level - {g}")
        response1 = await self._send_command(f">setlevel,{channel + 1},{g}\r\n")
        _LOGGER.debug(f"Setting B channel - channel {channel + 2}, level - {b}")
        response2 = await self._send_command(f">setlevel,{channel + 2},{b}\r\n")
        _LOGGER.debug(f"Setting W channel - channel {channel + 3}, level - {w}")
        response3 = await self._send_command(f">setlevel,{channel + 3},{w}\r\n")
        return (
            "ok" in response
            and "ok" in response1
            and "ok" in response2
            and "ok" in response3
        )

    async def set_rgbww(
        self, channel: int, rgbww: tuple[int, int, int, int, int]
    ) -> bool:
        """Set the RGBWW color of a specific channel."""
        r, g, b, w1, w2 = rgbww
        _LOGGER.debug(f"Setting R channel - channel {channel}, level - {r}")
        response = await self._send_command(f">setlevel,{channel},{r}\r\n")
        _LOGGER.debug(f"Setting G channel - channel {channel + 1}, level - {g}")
        response1 = await self._send_command(f">setlevel,{channel + 1},{g}\r\n")
        _LOGGER.debug(f"Setting B channel - channel {channel + 2}, level - {b}")
        response2 = await self._send_command(f">setlevel,{channel + 2},{b}\r\n")
        _LOGGER.debug(f"Setting W1 channel - channel {channel + 3}, level - {w1}")
        response3 = await self._send_command(f">setlevel,{channel + 3},{w1}\r\n")
        _LOGGER.debug(f"Setting W2 channel - channel {channel + 4}, level - {w2}")
        response4 = await self._send_command(f">setlevel,{channel + 4},{w2}\r\n")
        return (
            "ok" in response
            and "ok" in response1
            and "ok" in response2
            and "ok" in response3
            and "ok" in response4
        )
