"""Message."""

from __future__ import annotations

from typing import TypeVar


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


class ZoneEnabledMsg(LeaMessage):
    """Zone enabled msg."""

    command = "enable"
    request_type = "get "
    ext1 = "/amp/channels/"
    ext2 = "/output/enable"

    def __init__(self, zone_id) -> None:
        """Init."""
        super().__init__(self.as_dict(zone_id))


class OnOffMessage(LeaMessage):
    """OnOffMsg."""

    command = "enable"
    request_type = "set "
    ext1 = "/amp/channels/"
    ext2 = "/output/enable"

    def __init__(self, zone_id, command) -> None:
        """Init."""
        super().__init__(self.as_dict(zone_id, command))


class getVolumeMessage(LeaMessage):
    """Get volume msgs."""

    command = "fader"
    request_type = "get "
    ext1 = "/amp/channels/"
    ext2 = "/output/fader"

    def __init__(self, zone_id) -> None:
        """Init."""
        super().__init__(self.as_dict(zone_id, ""))


class setVolumeMessage(LeaMessage):
    """Set Volume Message."""

    command = "fader"
    request_type = "set "
    ext1 = "/amp/channels/"
    ext2 = "/output/fader"

    def __init__(self, zone_id, volume) -> None:
        """Init."""
        super().__init__(self.as_dict(zone_id, volume))


class getMuteMessage(LeaMessage):
    """Get Mute Message."""

    command = "mute"
    request_type = "get "
    ext1 = "/amp/channels/"
    ext2 = "/output/mute"

    def __init__(self, zone_id) -> None:
        """Init."""
        super().__init__(self.as_dict(zone_id, ""))


class setMuteMessage(LeaMessage):
    """Set Mute Message."""

    command = "mute"
    request_type = "set "
    ext1 = "/amp/channels/"
    ext2 = "/output/mute"

    def __init__(self, zone_id, mute) -> None:
        """Init."""
        super().__init__(self.as_dict(zone_id, mute))


class getSourceMessage(LeaMessage):
    """Get Source Message."""

    command = "source"
    request_type = "get "
    ext1 = "/amp/channels/"
    ext2 = "/inputSelector/primary"

    def __init__(self, zone_id) -> None:
        """Init."""
        super().__init__(self.as_dict(zone_id, ""))


class setSourceMessage(LeaMessage):
    """Set source Message."""

    command = "source"
    request_type = "set "
    ext1 = "/amp/channels/"
    ext2 = "/inputSelector/primary"

    def __init__(self, zone_id, source) -> None:
        """Init."""
        super().__init__(self.as_dict(zone_id, source))


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

        if not value:
            return None

        return zoneId, command_type, value
