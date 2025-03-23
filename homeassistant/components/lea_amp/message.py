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


class GetNumOfInputsMessage(LeaMessage):
    """Get Num of inputs."""

    command = "numInputs"
    request_type = "get "
    ext1 = "/amp/deviceInfo/numInputs"
    ext2 = ""

    def __init__(self) -> None:
        """Init."""
        super().__init__(self.as_dict("", ""))


class ZoneEnabledMsg(LeaMessage):
    """Zone enabled msg."""

    request_type = "get "
    ext1 = "/amp/channels/"
    ext2 = "/output/enable"

    def __init__(self, zone_id, command) -> None:
        """Init."""
        super().__init__(self.as_dict(zone_id, command))


class OnOffMessage(LeaMessage):
    """OnOffMsg."""

    request_type = "set "
    ext1 = "/amp/channels/"
    ext2 = "/output/enable"

    def __init__(self, zone_id, command) -> None:
        """Init."""
        super().__init__(self.as_dict(zone_id, command))


class getVolumeMessage(LeaMessage):
    """Get volume msgs."""

    request_type = "get "
    ext1 = "/amp/channels/"
    ext2 = "/output/fader"

    def __init__(self, zone_id) -> None:
        """Init."""
        super().__init__(self.as_dict(zone_id, ""))


class setVolumeMessage(LeaMessage):
    """Set Volume Message."""

    request_type = "set "
    ext1 = "/amp/channels/"
    ext2 = "/output/fader"

    def __init__(self, zone_id, volume) -> None:
        """Init."""
        super().__init__(self.as_dict(zone_id, volume))


class getMuteMessage(LeaMessage):
    """Get Mute Message."""

    request_type = "get "
    ext1 = "/amp/channels/"
    ext2 = "/output/mute"

    def __init__(self, zone_id) -> None:
        """Init."""
        super().__init__(self.as_dict(zone_id, ""))


class setMuteMessage(LeaMessage):
    """Set Mute Message."""

    request_type = "set "
    ext1 = "/amp/channels/"
    ext2 = "/output/mute"

    def __init__(self, zone_id, mute) -> None:
        """Init."""
        super().__init__(self.as_dict(zone_id, mute))


class getSourceMessage(LeaMessage):
    """Get Source Message."""

    request_type = "get "
    ext1 = "/amp/channels/"
    ext2 = "/inputSelector/primary"

    def __init__(self, zone_id) -> None:
        """Init."""
        super().__init__(self.as_dict(zone_id, ""))


class setSourceMessage(LeaMessage):
    """Set source Message."""

    request_type = "set "
    ext1 = "/amp/channels/"
    ext2 = "/inputSelector/primary"

    def __init__(self, zone_id, source) -> None:
        """Init."""
        super().__init__(self.as_dict(zone_id, source))


class ScanResponse(LeaMessage):
    """Scan Response."""

    command = "scan"

    # def __init__(self, data: str) -> None:
    # """Init."""
    # super().__init__(data)

    @property
    def zone(self):
        """Zone."""
        return self._data


class DevStatusResponse(LeaMessage):
    """Dev Status Response."""

    command = "devStatus"

    # def __init__(self, data: str) -> None:
    # """Init."""
    # super().__init__(data)

    @property
    def power(self) -> bool:  # noqa: D102
        return bool(self._data)

    @property
    def volume(self) -> int:  # noqa: D102
        return int(self._data)

    @property
    def mute(self) -> bool:  # noqa: D102
        return bool(self._data)

    @property
    def source(self) -> int:  # noqa: D102
        return int(self._data)


class StatusResponse(LeaMessage):
    """Status Response."""

    command = "status"

    '''def __init__(self, data: str) -> None:
        """Init."""
        super().__init__(data)'''


class MessageResponseFactory:
    """Message Response Factory."""

    def __init__(self) -> None:
        """Init."""
        self._messages: set[type[LeaMessage]] = {
            DevStatusResponse,
            StatusResponse,
        }

        def create_message(self, data: str):
            if "deviceName" in data:
                zoneId = "0"
                value = data[data.find("deviceName") + 12 : len(data) - 2]
                command_type = "deviceName"
            elif "numInputs" in data:
                zoneId = "0"
                value = data.replace("/amp/deviceInfo/numInputs", "")
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
                zoneId = data[
                    data.find("channels/") + 9 : data.find("/inputSelector") - 1
                ]

                value = data[data.find("primary") + 9 : len(data) - 2]
                value = data.replace('"', "")
                command_type = "source"
            value = value.replace(" ", "")

            # message_data = []

            if not value:
                return None
            # message_data = [value, command_type, zoneId]
            return value, zoneId, command_type
