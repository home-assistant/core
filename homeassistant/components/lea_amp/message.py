"""Message."""

from __future__ import annotations

import logging
from typing import TypeVar

_LOGGER = logging.getLogger(__name__)


class LeaMessage:
    """Lea Message."""

    request_type: str = ""
    ext1: str = ""
    ext2: str = ""
    _data: str

    def __init__(self, data: str) -> None:
        """Init."""
        self._data = data

    def as_dict(self, zone_id: str = "", command: str = ""):
        """Dictionary."""  # noqa: D401
        return str(
            self.request_type
            + self.ext1
            + zone_id
            + "/"
            + self.ext2
            + " "
            + command
            + "\n"
        )

    @property
    def data(self) -> str:
        """Return zone data."""
        return self._data


M = TypeVar("M", bound=LeaMessage)


def GetNumOfInputsMessage():
    """Get Num of inputs."""

    request_type = "get "
    ext1 = "/amp/deviceInfo/numInputs"

    return request_type + ext1 + "\n"


def ZoneEnabledMsg(zone_id: str) -> str:
    """Zone enabled msg."""

    request_type = "get "
    ext1 = "/amp/channels/"
    ext2 = "/output/enable"

    return request_type + ext1 + zone_id + ext2 + "\n"


def OnOffMessage(zone_id: str, value: str) -> str:
    """OnOffMsg."""

    request_type = "set "
    ext1 = "/amp/channels/"
    ext2 = "/output/enable"
    return request_type + ext1 + zone_id + ext2 + " " + value + "\n"


def getVolumeMessage(zone_id: str) -> str:
    """Get volume msgs."""

    request_type = "get "
    ext1 = "/amp/channels/"
    ext2 = "/output/fader"

    return request_type + ext1 + zone_id + ext2 + "\n"


def setVolumeMessage(zone_id: str, volume: int) -> str:
    """Set Volume Message."""

    request_type = "set "
    ext1 = "/amp/channels/"
    ext2 = "/output/fader"

    return request_type + ext1 + zone_id + ext2 + " " + str(volume) + "\n"


def getMuteMessage(zone_id: str) -> str:
    """Get Mute Message."""

    request_type = "get "
    ext1 = "/amp/channels/"
    ext2 = "/output/mute"

    return request_type + ext1 + zone_id + ext2 + "\n"


def setMuteMessage(zone_id: str, mute: bool) -> str:
    """Set Mute Message."""

    request_type = "set "
    ext1 = "/amp/channels/"
    ext2 = "/output/mute"

    return request_type + ext1 + zone_id + ext2 + " " + str(mute) + "\n"


def getSourceMessage(zone_id: str) -> str:
    """Get Source Message."""

    request_type = "get "
    ext1 = "/amp/channels/"
    ext2 = "/inputSelector/primary"

    return request_type + ext1 + zone_id + ext2 + "\n"


def setSourceMessage(zone_id: str, source: int) -> str:
    """Set source Message."""

    request_type = "set "
    ext1 = "/amp/channels/"
    ext2 = "/inputSelector/primary"

    return request_type + ext1 + zone_id + ext2 + " " + str(source) + "\n"


class ScanResponse(LeaMessage):
    """Scan Response."""

    command = "scan"

    @property
    def id(self):
        """Id."""
        return self._data

    @property
    def zone(self):
        """Zone."""
        return self._data


class DevStatusResponse(LeaMessage):
    """Dev Status Response."""

    command = "devStatus"

    """def __init__(self, data: dict[str, Any]) -> None:
        Init
        super().__init__(data)"""


class StatusResponse(LeaMessage):
    """Status Response."""

    command = "status"

    """def __init__(self, data: dict[str, Any]) -> None:
        Init
        super().__init__(data)"""


class MessageResponseFactory:
    """Message Response Factory."""

    def __init__(self) -> None:
        """Init."""
        self._messages: set[type[LeaMessage]] = {
            DevStatusResponse,
            ScanResponse,
        }

    def create_message(self, data: str):
        """Create message."""
        if "deviceName" in data:
            zoneId = "0"
            value = data[data.find("deviceName") + 12 : len(data) - 2]
            command_type = "deviceName"
        elif "numInputs" in data:
            zoneId = "0"
            value = data.replace("/amp/deviceInfo/numInputs", "")
            command_type = "numInputs"
        elif "output/name" in data:
            zoneId = data[data.find("channels/") + 9 : data.find("/output") - 1]
            value = data[data.find("output/name") + 13 : len(data) - 2]

            command_type = "zoneName"
        elif "output/fader" in data:
            zoneId = data[data.find("channels/") + 9 : data.find("/output") - 1]

            value = data.replace("/amp/channels/" + zoneId + "/output/fader", "")
            value = data.replace('"', "")
            command_type = "volume"
        elif "output/mute" in data:
            zoneId = data[data.find("channels/") + 9 : data.find("/output") - 1]

            value = data.replace("/amp/channels/" + zoneId + "/output/mute", "")
            value = data.replace('"', "")
            command_type = "mute"
        elif "output/enable" in data:
            zoneId = data[data.find("channels/") + 9 : data.find("/output") - 1]

            value = data.replace("/amp/channels/" + zoneId + "/output/enable", "")
            value = data.replace('"', "")
            command_type = "power"
        elif "inputSelector/primary" in data:
            zoneId = data[data.find("channels/") + 9 : data.find("/inputSelector") - 1]

            value = data[data.find("primary") + 9 : len(data) - 2]
            value = data.replace('"', "")
            command_type = "source"
        value = value.replace(" ", "")

        _LOGGER.log(logging.INFO, "value: %s", str(value))
        _LOGGER.log(logging.INFO, "command_type: %s", str(command_type))
        _LOGGER.log(logging.INFO, "zoneId: %s", str(zoneId))
        if not value:
            return None

        return zoneId, command_type, value
