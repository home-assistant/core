"""The engine that connects to a LC7001 hub."""

from enum import StrEnum, auto
import json
import logging
import re
import socket
from threading import Lock, Thread
from typing import Any

from pymitter import EventEmitter

from .diagnostics import BroadcastMemory
from .packet import Packet
from .system import ReportSystemProperties, SystemInfo
from .utils import encrypt
from .zone import ListZones, ReportZoneProperties, ZonePropertyList

_LOGGER = logging.getLogger(__name__)

PACKET_DELIMITER = "\x00"
PACKET_DELIMITER_BYTES = b"\x00"
REGEX_HELLO = r"^Hello V1[ \r\n]*"
REGEX_CHALLENGE = r"^([0-9A-F]{32}) [0-9A-F]{12}[ \r\n]*"
REGEX_ACCEPTED = r"\[OK\][ \r\n]*"


class ConnectionState(StrEnum):
    """The possible states of the connection to the LC7001."""

    Disconnected = auto()
    Connected = auto()
    Hello = auto()
    Challenged = auto()
    Authenticated = auto()
    Ready = auto()


def createPacket(jsonString: str) -> Packet | None:
    """Create the proper packet from a JSON string."""
    try:
        packetDict = json.loads(jsonString)
    except json.JSONDecodeError:
        return None

    match packetDict.get("Service"):
        case "ListZones":
            return ListZones(**packetDict)

        case "ReportZoneProperties" | "ZonePropertiesChanged":
            return ReportZoneProperties(**packetDict)

        case "ReportSystemProperties" | "SystemPropertiesChanged":
            return ReportSystemProperties(**packetDict)

        case "BroadcastMemory":
            return BroadcastMemory(**packetDict)

        case "SystemInfo":
            return SystemInfo(**packetDict)

        case _:
            # _LOGGER.warning("Unknown packet: %s", json.dumps(packetDict, indent=4))
            pass

    return None


class Engine(EventEmitter):
    """The engine that connects to a LC7001 hub."""

    def __init__(
        self, password: str, host: str = "LCM1.local", port: int = 2112
    ) -> None:
        """Initialize an Engine instance."""
        super().__init__()

        self.thread: Thread | None = None
        self.running = False
        self.host = host
        self.port = port
        self.password = password
        self.state: ConnectionState = ConnectionState.Disconnected
        self.connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.zones: dict[int, ZonePropertyList] = {}
        self._expectedZoneCount = 0
        self.packetID = 0
        self.systemInfo = SystemInfo()
        self.systemProperties: dict[str, Any] = {}

    def connect(self) -> None:
        """Connect to the LC7001 hub."""
        self.connection.connect((self.host, self.port))
        self._changeState(ConnectionState.Connected)

    def disconnect(self) -> None:
        """Disconnect from the LC7001 hub."""
        self.connection.close()
        self._changeState(ConnectionState.Disconnected)

    def _changeState(self, newState: ConnectionState) -> None:
        if self.state is not newState:
            previousState = self.state
            self.state = newState
            self.emit("StateChanged", newState=newState, previousState=previousState)

    async def waitForState(
        self, stateToWaitFor: ConnectionState, timeout: float = 10.0
    ) -> None:
        """Wait for a specific state for a certain time."""

        lock = Lock()

        # pylint: disable-next=consider-using-with
        lock.acquire()

        @self.on("StateChanged")
        def onStateChanged(
            newState: ConnectionState, previousState: ConnectionState
        ) -> None:
            if newState == stateToWaitFor:
                lock.release()

        try:
            # pylint: disable-next=consider-using-with
            lock.acquire(blocking=True, timeout=timeout)
        finally:
            self.off("StateChanged", onStateChanged)

    def _generatePacketID(self) -> int:
        packetID = self.packetID
        self.packetID += 1
        return packetID

    def sendPacket(self, packet: Packet) -> None:
        """Send a packet to the LC7001 hub."""
        packet.setID(self._generatePacketID())
        self.connection.send(packet.toBytes())
        self.connection.send(PACKET_DELIMITER.encode())

    def _processMessage(self, message: str) -> None:
        packet = createPacket(message)

        if packet is None:
            pass
        if isinstance(packet, ListZones):
            for zone in packet.ZoneList:
                if zone.ZID is not None:
                    self.sendPacket(ReportZoneProperties(ZID=zone.ZID))
            self._expectedZoneCount = len(packet.ZoneList)

        elif isinstance(packet, ReportZoneProperties):
            if packet.PropertyList is not None and packet.ZID is not None:
                if packet.ZID in self.zones:
                    self.zones[packet.ZID].applyChanges(packet.PropertyList)
                else:
                    self.zones[packet.ZID] = packet.PropertyList

                try:
                    self.emit(
                        "ZoneChanged",
                        ZID=packet.ZID,
                        changes=ZonePropertyList(packet.PropertyList),
                        properties=self.zones[packet.ZID],
                    )
                except Exception:
                    _LOGGER.exception("Could not emit ZoneChanged")

            if len(self.zones.items()) >= self._expectedZoneCount:
                self._changeState(ConnectionState.Ready)

        elif isinstance(packet, BroadcastMemory):
            self.emit("BroadcastMemory", memory=vars(packet))

        elif isinstance(packet, ReportSystemProperties):
            if packet.PropertyList:
                self.systemProperties = packet.PropertyList
                self.emit("SystemPropertiesChanged", properties=self.systemProperties)

        elif isinstance(packet, SystemInfo):
            self.systemInfo = packet

        else:
            pass

    def _loop(self) -> None:
        """Run the message loop."""
        message = ""
        while self.running:
            messages = self.connection.recv(2048).split(PACKET_DELIMITER_BYTES)
            for currentMessageAsBytes in messages:
                currentMessage = currentMessageAsBytes.decode().replace(
                    PACKET_DELIMITER, ""
                )
                if currentMessage == "":
                    continue
                message += currentMessage

                match self.state:
                    case ConnectionState.Connected:
                        m = re.search(REGEX_HELLO, message)
                        if m:
                            self._changeState(ConnectionState.Hello)
                            message = ""

                    case ConnectionState.Hello:
                        m = re.search(REGEX_CHALLENGE, message)
                        if m:
                            self._changeState(ConnectionState.Challenged)
                            challenge = m.group(1)
                            self.connection.send(encrypt(self.password, challenge))
                            message = ""

                    case ConnectionState.Challenged:
                        m = re.search(REGEX_ACCEPTED, message)
                        if m:
                            self._changeState(ConnectionState.Authenticated)
                            message = ""

                            self.sendPacket(SystemInfo())
                            self.sendPacket(ReportSystemProperties())
                            self.sendPacket(ListZones())

                    case ConnectionState.Authenticated | ConnectionState.Ready:
                        try:
                            self._processMessage(message)
                        except Exception:
                            _LOGGER.exception("Raw message: %s", currentMessage)
                            raise
                        message = ""

    def start(self) -> None:
        """Start the LC7001 engine."""
        if self.thread is None:
            self.running = True
            self.thread = Thread(target=self._loop)
            self.thread.start()

    async def stop(self) -> None:
        """Stop the LC7001 engine."""
        if self.thread:
            self.running = False
            self.thread.join()
            self.thread = None
