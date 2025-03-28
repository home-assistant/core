"""A BroadcastMemory packet."""

import logging
from typing import Any

from .packet import Packet

_LOGGER = logging.getLogger(__name__)


class ReportSystemProperties(Packet):
    """A SystemProperties packet."""

    def __init__(
        self,
        ID: int | None = None,
        Service: str | None = None,
        PropertyList: dict | None = None,
        **kwargs,
    ) -> None:
        """Initialize."""
        super().__init__(ID=ID, Service=Service or "ReportSystemProperties", **kwargs)
        self.PropertyList = PropertyList

    def asDict(self) -> dict[str, Any]:
        """Return a dict representation of packet."""
        selfDict = super().asDict()

        if self.PropertyList is not None:
            selfDict["PropertyList"] = self.PropertyList

        return selfDict


class SystemInfo(Packet):
    """Represents a SystemInfo packet from LC7001."""

    def __init__(
        self, ID: int | None = None, Service: str | None = None, **kwargs
    ) -> None:
        """Initialize."""
        super().__init__(ID=ID, Service=Service or "SystemInfo", **kwargs)

        self.Model = kwargs.get("Model")
        self.FirmwareVersion = kwargs.get("FirmwareVersion")
        self.FirmwareDate = kwargs.get("FirmwareDate")
        self.FirmwareBranch = kwargs.get("FirmwareBranch")
        self.MACAddress = kwargs.get("MACAddress")
        self.UpdateState = kwargs.get("UpdateState")

    def asDict(self) -> dict[str, Any]:
        """Return a dict representation of packet."""
        selfDict = super().asDict()

        if self.Model is not None:
            selfDict["Model"] = self.Model

        if self.FirmwareVersion is not None:
            selfDict["FirmwareVersion"] = self.FirmwareVersion

        if self.FirmwareDate is not None:
            selfDict["FirmwareDate"] = self.FirmwareDate

        if self.FirmwareBranch is not None:
            selfDict["FirmwareBranch"] = self.FirmwareBranch

        if self.MACAddress is not None:
            selfDict["MACAddress"] = self.MACAddress

        if self.UpdateState is not None:
            selfDict["UpdateState"] = self.UpdateState

        return selfDict
