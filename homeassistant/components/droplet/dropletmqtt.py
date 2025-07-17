"""Droplet API."""

from dataclasses import dataclass
import json
import logging
import socket
import ssl

import aiohttp


class DropletConnection:
    """Connection to Droplet device."""

    DEFAULT_PORT = 443

    @staticmethod
    async def get_client(
        session: aiohttp.client.ClientSession, host: str, port: int | None, token: str
    ) -> aiohttp.ClientWebSocketResponse:
        """Create connection to Droplet device."""
        url = f"wss://{host}:{port if port else DropletConnection.DEFAULT_PORT}/ws"
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        headers = {"Authorization": token}
        return await session.ws_connect(
            url=url, ssl_context=ssl_context, headers=headers, heartbeat=10
        )


class DropletDiscovery:
    """Store Droplet discovery information."""

    device_id: str | None
    host: str
    port: int | None
    properties: dict

    def __init__(
        self, host: str, port: int | None, service_name: str, properties: dict
    ) -> None:
        """Initialize Droplet discovery."""
        self.host = host
        self.port = port
        try:
            self.device_id = service_name.split(".")[0]
        except IndexError:
            self.device_id = None

        self.properties = properties

    def is_valid(self) -> bool:
        """Check discovery validity."""
        if self.device_id is None or self.port is None or self.port < 1:
            return False
        return True

    async def try_connect(
        self, session: aiohttp.client.ClientSession, pairing_code: str
    ) -> bool:
        """Try to connect to Droplet with provided credentials."""
        client = None
        try:
            client = await DropletConnection.get_client(
                session, self.host, self.port, pairing_code
            )
            res = await client.receive(timeout=1)
            if not res or res.type in [
                aiohttp.WSMsgType.CLOSE,
                aiohttp.WSMsgType.CLOSED,
            ]:
                return False
        except (
            aiohttp.WSServerHandshakeError,
            aiohttp.ClientConnectionError,
            socket.gaierror,
        ):
            return False
        finally:
            if client:
                await client.close()
        return True


@dataclass
class Droplet:
    """Droplet device."""

    host: str
    session: aiohttp.client.ClientSession
    token: str
    port: int = 80
    logger: logging.Logger | None = None

    _flow_rate: float = 0
    _signal_quality: str = "Unknown"
    _server_status: str = "Unknown"
    _available: bool = False

    _client: aiohttp.ClientWebSocketResponse | None = None
    _connected: bool = False

    @property
    def connected(self) -> bool:
        """Return true if we are connected to Droplet."""
        return self._client is not None and not self._client.closed

    async def connect(self) -> bool:
        """Connect to Droplet."""
        self._log(logging.ERROR, "Connecting")
        if self._connected:
            return True

        if not self.session:
            return False

        try:
            self._client = await DropletConnection.get_client(
                self.session, self.host, self.port, self.token
            )
        except (
            aiohttp.WSServerHandshakeError,
            aiohttp.ClientConnectionError,
            socket.gaierror,
        ) as ex:
            self._log(logging.ERROR, "Failed to open connection: %s", str(ex))
            self._available = False
            return False

        self._available = True
        return True

    async def disconnect(self) -> None:
        """Disconnect from WebSocket."""
        self._log(logging.ERROR, "Disconnect")
        self._available = False
        if self._client:
            await self._client.close()
            self._connected = False

    async def listen(self, callback) -> None:
        """Listen for messages over the websocket."""
        while self._client and not self._client.closed:
            message = await self._client.receive()
            match message.type:
                case aiohttp.WSMsgType.ERROR:
                    self._log(logging.ERROR, "Received error message")
                    await self.disconnect()
                    return
                case aiohttp.WSMsgType.TEXT:
                    try:
                        if self._parse_message(message.json()):
                            self._available = True
                            callback(None)
                    except json.JSONDecodeError:
                        pass
                case aiohttp.WSMsgType.CLOSE | aiohttp.WSMsgType.CLOSED:
                    self._log(logging.ERROR, "Connection closed!")
                    await self.disconnect()
                    return
                case _:
                    self._log(
                        logging.ERROR,
                        f"Msg type: {aiohttp.WSMsgType(message.type).name}",
                    )

    def _parse_message(self, msg: dict) -> bool:
        """Parse state message and return true if anything changed."""
        changed = False
        if flow_rate := msg.get("flow"):
            self._flow_rate = flow_rate
            changed = True
        if network := msg.get("server"):
            self._server_status = network
            changed = True
        if signal := msg.get("signal"):
            self._signal_quality = signal
            changed = True
        return changed

    def _log(self, level, msg, *args) -> None:
        """Log a message, if a logger is available."""
        if not self.logger:
            return
        self.logger.log(level, msg, *args)

    def get_flow_rate(self):
        """Get Droplet's flow rate."""
        return self._flow_rate

    def get_signal_quality(self):
        """Get Droplet's signal quality."""
        return self._signal_quality

    def get_server_status(self):
        """Get Droplet's server status."""
        return self._server_status

    def get_availability(self):
        """Return true if Droplet device is available."""
        return self._available
